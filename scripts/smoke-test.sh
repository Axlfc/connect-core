#!/bin/bash
# ========================================
# cognito-stack - Smoke Test Script
# ========================================
# Run a quick smoke test of the Docker Compose stack
# Usage: ./scripts/smoke-test.sh [profile]

set -e

PROFILE="${1:-cpu}"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo ""
    echo "================================================"
    echo -e "${BLUE}$1${NC}"
    echo "================================================"
    echo ""
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# ========================================
# Setup
# ========================================
print_header "Smoke Test - Profile: $PROFILE"

cd "$PROJECT_ROOT"

# Validate docker-compose
print_info "Validating docker-compose.yml..."
if docker compose config --quiet 2>/dev/null; then
    print_success "docker-compose.yml is valid"
else
    print_error "docker-compose.yml has errors"
    exit 1
fi

# ========================================
# Start Services
# ========================================
print_header "Starting Services"

print_info "Pulling necessary images..."
docker compose --profile "$PROFILE" pull --quiet 2>/dev/null || true

print_info "Starting services..."
docker compose --profile "$PROFILE" up -d --wait 2>/dev/null || {
    print_error "Failed to start services"
    docker compose logs --tail 50
    exit 1
}

sleep 5

# ========================================
# Health Checks
# ========================================
print_header "Running Health Checks"

check_service() {
    local service=$1
    local port=$2
    local endpoint=$3
    
    print_info "Checking $service..."
    
    if [ -n "$endpoint" ]; then
        # HTTP endpoint check
        if curl -sf "http://localhost:$port$endpoint" > /dev/null 2>&1; then
            print_success "$service is healthy"
            return 0
        fi
    else
        # Container running check
        if docker exec "$service" true 2>/dev/null; then
            print_success "$service is running"
            return 0
        fi
    fi
    
    print_error "$service failed health check"
    return 1
}

# Check critical services
services_ok=true

check_service "postgres" "5432" "" || services_ok=false
check_service "redis" "6379" "" || services_ok=false
check_service "qdrant" "6333" "" || services_ok=false

# Check optional services based on profile
if [ "$PROFILE" != "cpu" ]; then
    check_service "comfyui" "8188" "" || services_ok=false
fi

sleep 5

check_service "n8n" "5678" "/healthz" || services_ok=false

# ========================================
# API Tests
# ========================================
print_header "Testing APIs"

# Test n8n API
print_info "Testing n8n API..."
if curl -sf http://localhost:5678/api/v1/me > /dev/null 2>&1; then
    print_success "n8n API is responding"
else
    print_warning "n8n API not yet ready (may be initializing)"
fi

# Test Ollama API
print_info "Testing Ollama API..."
if curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
    print_success "Ollama API is responding"
else
    print_error "Ollama not available"
    services_ok=false
fi

# Test Qdrant API
print_info "Testing Qdrant API..."
if curl -sf http://localhost:6333/health > /dev/null 2>&1; then
    print_success "Qdrant API is responding"
else
    print_error "Qdrant not available"
    services_ok=false
fi

# ========================================
# Cleanup
# ========================================
print_header "Cleanup"

print_info "Stopping services..."
docker compose --profile "$PROFILE" down --timeout 10 > /dev/null 2>&1

# ========================================
# Summary
# ========================================
echo ""
print_header "Smoke Test Summary"

if [ "$services_ok" = true ]; then
    print_success "All smoke tests passed!"
    echo ""
    exit 0
else
    print_error "Some smoke tests failed"
    echo ""
    exit 1
fi
