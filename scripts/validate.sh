#!/bin/bash
# ========================================
# cognito-stack - Local Validation Script
# ========================================
# Run all validation checks locally before committing
# Usage: ./scripts/validate.sh [options]

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Counters
PASSED=0
FAILED=0
WARNINGS=0

print_header() {
    echo ""
    echo "================================================"
    echo -e "${BLUE}$1${NC}"
    echo "================================================"
    echo ""
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
    ((PASSED++))
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
    ((FAILED++))
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
    ((WARNINGS++))
}

# ========================================
# YAML Validation
# ========================================
validate_yaml() {
    print_header "Validating YAML Files"
    
    if ! command -v python3 &> /dev/null; then
        print_warning "Python3 not found, skipping YAML validation"
        return
    fi
    
    # Check docker-compose.yml
    if python3 -c "import yaml; yaml.safe_load(open('$PROJECT_ROOT/docker-compose.yml'))" 2>/dev/null; then
        print_success "docker-compose.yml is valid YAML"
    else
        print_error "docker-compose.yml has YAML syntax errors"
    fi
}

# ========================================
# JSON Validation
# ========================================
validate_json() {
    print_header "Validating JSON Files"
    
    if ! command -v python3 &> /dev/null; then
        print_warning "Python3 not found, skipping JSON validation"
        return
    fi
    
    # Check n8n-task-runners.json
    if python3 -c "import json; json.load(open('$PROJECT_ROOT/n8n-task-runners.json'))" 2>/dev/null; then
        print_success "n8n-task-runners.json is valid JSON"
    else
        print_error "n8n-task-runners.json has JSON syntax errors"
    fi
}

# ========================================
# Shell Script Linting
# ========================================
lint_shell() {
    print_header "Linting Shell Scripts"
    
    if ! command -v shellcheck &> /dev/null; then
        print_warning "shellcheck not found (install with: apt-get install shellcheck)"
        return
    fi
    
    for script in start.sh stop.sh uninitialize_env.sh update-zrok-url.sh n8n-entrypoint.sh; do
        if [ -f "$PROJECT_ROOT/$script" ]; then
            if shellcheck -x "$PROJECT_ROOT/$script" 2>/dev/null; then
                print_success "$script has no shell errors"
            else
                print_warning "$script has shellcheck warnings"
            fi
        fi
    done
}

# ========================================
# Dockerfile Linting
# ========================================
lint_dockerfile() {
    print_header "Linting Dockerfiles"
    
    if ! command -v hadolint &> /dev/null; then
        print_warning "hadolint not found (install with: apt-get install hadolint)"
        return
    fi
    
    for dockerfile in Dockerfile.n8n Dockerfile.runners Dockerfile.comfyui Dockerfile.matrix; do
        if [ -f "$PROJECT_ROOT/$dockerfile" ]; then
            if hadolint "$PROJECT_ROOT/$dockerfile" 2>/dev/null; then
                print_success "$dockerfile passes linting"
            else
                print_warning "$dockerfile has hadolint warnings"
            fi
        fi
    done
}

# ========================================
# Docker Compose Validation
# ========================================
validate_compose() {
    print_header "Validating Docker Compose"
    
    if ! command -v docker &> /dev/null; then
        print_warning "Docker not found, skipping docker-compose validation"
        return
    fi
    
    cd "$PROJECT_ROOT"
    
    if docker compose config --quiet 2>/dev/null; then
        print_success "docker-compose.yml is valid"
        
        # Count services
        service_count=$(docker compose config --quiet 2>/dev/null | grep -c "^  [a-z]" || echo "0")
        echo -e "${BLUE}Services defined: $service_count${NC}"
    else
        print_error "docker-compose.yml has syntax errors"
    fi
}

# ========================================
# Configuration Validation
# ========================================
validate_config() {
    print_header "Validating Configuration"
    
    # Check .env.example
    if [ -f "$PROJECT_ROOT/.env.example" ]; then
        var_count=$(grep -c "^[A-Z_]*=" "$PROJECT_ROOT/.env.example" || echo "0")
        print_success ".env.example found with $var_count variables"
        
        # Check critical variables
        critical_vars=(
            "POSTGRES_PASSWORD"
            "REDIS_PASSWORD"
            "N8N_ENCRYPTION_KEY"
            "N8N_RUNNERS_AUTH_TOKEN"
        )
        
        for var in "${critical_vars[@]}"; do
            if grep -q "^$var=" "$PROJECT_ROOT/.env.example"; then
                echo -e "  ${GREEN}✓${NC} $var configured"
            else
                echo -e "  ${RED}✗${NC} Missing $var"
            fi
        done
    else
        print_error ".env.example not found"
    fi
}

# ========================================
# Port Binding Validation
# ========================================
validate_ports() {
    print_header "Validating Port Assignments"
    
    local expected_ports=(5432 5678 5679 6333 6379 8008 8188 11434)
    local found_ports=0
    
    for port in "${expected_ports[@]}"; do
        if grep -q "$port:" "$PROJECT_ROOT/docker-compose.yml"; then
            echo -e "  ${GREEN}✓${NC} Port $port configured"
            ((found_ports++))
        else
            echo -e "  ${YELLOW}⚠${NC} Port $port not found"
        fi
    done
    
    echo ""
    print_success "Found $found_ports/$((${#expected_ports[@]})) expected ports"
}

# ========================================
# Security Checks
# ========================================
security_checks() {
    print_header "Security Checks"
    
    # Check for committed .env file
    if [ -f "$PROJECT_ROOT/.env" ]; then
        print_warning ".env file found in repo (should be .env.example only)"
    else
        print_success ".env file not in repo (good)"
    fi
    
    # Check for exposed credentials
    if grep -r "sk_live_\|pk_live_" "$PROJECT_ROOT" --include="*.yml" --include="*.yaml" --include="*.sh" 2>/dev/null; then
        print_error "Exposed API keys found in code"
    else
        print_success "No exposed API keys detected"
    fi
    
    # Check for hardcoded passwords in scripts
    if grep -r "password=" "$PROJECT_ROOT" --include="*.sh" | grep -v "POSTGRES_PASSWORD\|REDIS_PASSWORD" 2>/dev/null; then
        print_warning "Potential hardcoded passwords found in scripts"
    else
        print_success "No hardcoded passwords in scripts"
    fi
}

# ========================================
# Docker Images Check
# ========================================
check_images() {
    print_header "Checking Docker Images"
    
    if ! command -v docker &> /dev/null; then
        print_warning "Docker not found, skipping image check"
        return
    fi
    
    local images=(
        "n8nio/n8n:1.121.0"
        "postgres:16-alpine"
        "redis:7.2-alpine"
        "ollama/ollama:latest"
        "ghcr.io/ai-dock/comfyui:latest"
        "matrixdotorg/synapse:latest"
        "qdrant/qdrant:latest"
    )
    
    for image in "${images[@]}"; do
        if docker image inspect "$image" &>/dev/null 2>&1; then
            print_success "Image $image is available locally"
        else
            echo -e "  ${YELLOW}⚠${NC} Image $image not found locally (will be pulled on first run)"
        fi
    done
}

# ========================================
# File Completeness Check
# ========================================
check_files() {
    print_header "Checking Required Files"
    
    required_files=(
        "docker-compose.yml"
        ".env.example"
        "Dockerfile.n8n"
        "Dockerfile.runners"
        "Dockerfile.comfyui"
        "Dockerfile.matrix"
        "start.sh"
        "stop.sh"
        "uninitialize_env.sh"
        "n8n-entrypoint.sh"
        "n8n-task-runners.json"
        "README.md"
        "LICENSE.md"
    )
    
    for file in "${required_files[@]}"; do
        if [ -f "$PROJECT_ROOT/$file" ]; then
            print_success "$file exists"
        else
            print_error "$file missing"
        fi
    done
}

# ========================================
# Main Execution
# ========================================
main() {
    echo ""
    echo "========================================"
    echo "cognito-stack Local Validation"
    echo "========================================"
    echo "Project: $PROJECT_ROOT"
    echo ""
    
    # Run all checks
    check_files
    validate_yaml
    validate_json
    lint_shell
    lint_dockerfile
    validate_compose
    validate_config
    validate_ports
    security_checks
    check_images
    
    # Summary
    echo ""
    echo "========================================"
    echo -e "${BLUE}Validation Summary${NC}"
    echo "========================================"
    echo -e "${GREEN}Passed: $PASSED${NC}"
    [ $WARNINGS -gt 0 ] && echo -e "${YELLOW}Warnings: $WARNINGS${NC}"
    [ $FAILED -gt 0 ] && echo -e "${RED}Failed: $FAILED${NC}"
    echo ""
    
    if [ $FAILED -eq 0 ]; then
        echo -e "${GREEN}✓ All validations passed!${NC}"
        echo ""
        exit 0
    else
        echo -e "${RED}✗ Some validations failed!${NC}"
        echo ""
        exit 1
    fi
}

# Run main function
main "$@"
