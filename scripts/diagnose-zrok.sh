#!/bin/bash
# Zrok Diagnostic & Fix Script
# Comprehensive diagnostics and automatic fixes for zrok tunnel issues

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

print_header() {
    echo ""
    echo "========================================"
    echo -e "${BLUE}$1${NC}"
    echo "========================================"
}

print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }
print_info() { echo -e "${CYAN}ℹ️  $1${NC}"; }

print_header "🔍 Zrok Container Diagnostics & Fix"

# Get environment configuration
ENV_FILE=".env"
COMPOSE_FILE="docker-compose.yml"

# 1. Check if container exists and get actual name
print_header "1️⃣ Container Detection"
CONTAINER_NAME=""
for name in zrok-tunnel zrok-client; do
    if docker ps -a --format '{{.Names}}' | grep -q "^${name}$"; then
        CONTAINER_NAME="$name"
        print_success "Found container: $CONTAINER_NAME"
        break
    fi
done

if [ -z "$CONTAINER_NAME" ]; then
    print_error "No zrok container found (tried: zrok-tunnel, zrok-client)"
    print_info "Starting zrok container..."
    docker compose --profile zrok up -d 2>&1 | grep -v "attribute.*obsolete" || true
    sleep 5
    
    # Try again
    for name in zrok-tunnel zrok-client; do
        if docker ps -a --format '{{.Names}}' | grep -q "^${name}$"; then
            CONTAINER_NAME="$name"
            print_success "Started container: $CONTAINER_NAME"
            break
        fi
    done
    
    if [ -z "$CONTAINER_NAME" ]; then
        print_error "Failed to start zrok container"
        exit 1
    fi
fi

# Get container status
STATUS=$(docker inspect --format='{{.State.Status}}' "$CONTAINER_NAME")
RUNNING=$(docker inspect --format='{{.State.Running}}' "$CONTAINER_NAME")

echo "   Status: $STATUS"
echo "   Running: $RUNNING"

if [ "$STATUS" != "running" ]; then
    EXIT_CODE=$(docker inspect --format='{{.State.ExitCode}}' "$CONTAINER_NAME")
    print_error "Container exited with code: $EXIT_CODE"
fi

# 2. Check and display logs
print_header "📋 Container Logs Analysis"
LOGS=$(docker logs "$CONTAINER_NAME" 2>&1 | tail -30)
echo "$LOGS"

# Analyze logs for common issues
if echo "$LOGS" | grep -q "unauthorized"; then
    print_error "Authentication failed - check ZROK_AUTH_TOKEN"
elif echo "$LOGS" | grep -q "enable"; then
    print_warning "Zrok needs to be enabled first"
elif echo "$LOGS" | grep -q "share.*started"; then
    print_success "Zrok share appears to be active"
fi

# 3. Check .env configuration
print_header "📝 Environment Configuration"
if [ ! -f "$ENV_FILE" ]; then
    print_error ".env file not found"
    exit 1
fi

REQUIRED_VARS=("ZROK_API_ENDPOINT" "ZROK_AUTH_TOKEN" "ZROK_TARGET_URL")
MISSING_VARS=()

for VAR in "${REQUIRED_VARS[@]}"; do
    if grep -q "^${VAR}=" "$ENV_FILE"; then
        VALUE=$(grep "^${VAR}=" "$ENV_FILE" | cut -d'=' -f2 | tr -d '"' | tr -d "'")
        if [ -z "$VALUE" ]; then
            print_error "$VAR is set but EMPTY"
            MISSING_VARS+=("$VAR")
        else
            print_success "$VAR is configured"
            if [ "$VAR" != "ZROK_AUTH_TOKEN" ]; then
                echo "           Value: $VALUE"
            else
                echo "           Value: ${VALUE:0:10}...${VALUE: -4}"
            fi
        fi
    else
        print_error "$VAR is NOT set in .env"
        MISSING_VARS+=("$VAR")
    fi
done

# 4. Check zrok environment file
print_header "🔐 Zrok Environment Status"
if docker exec "$CONTAINER_NAME" test -f /home/zrok/.zrok/environment.json 2>/dev/null; then
    print_success "Zrok is enabled (environment.json exists)"
    echo ""
    echo "Environment preview:"
    docker exec "$CONTAINER_NAME" cat /home/zrok/.zrok/environment.json 2>/dev/null | head -5
else
    print_error "Zrok is NOT enabled (environment.json missing)"
    
    # Try to enable it
    if grep -q "^ZROK_AUTH_TOKEN=" "$ENV_FILE"; then
        TOKEN=$(grep "^ZROK_AUTH_TOKEN=" "$ENV_FILE" | cut -d'=' -f2 | tr -d '"' | tr -d "'")
        if [ -n "$TOKEN" ]; then
            print_info "Attempting to enable zrok with token from .env..."
            if docker exec "$CONTAINER_NAME" zrok enable "$TOKEN" 2>&1; then
                print_success "Zrok enabled successfully!"
            else
                print_error "Failed to enable zrok"
            fi
        fi
    fi
fi

# 5. Check .zrok directory
print_header "📁 Local .zrok Directory"
if [ -d ".zrok" ]; then
    print_success ".zrok directory exists"
    echo ""
    ls -lah .zrok/
else
    print_warning ".zrok directory does not exist"
    print_info "Creating .zrok directory..."
    mkdir -p .zrok
    chmod 755 .zrok
    print_success "Created .zrok directory"
fi

# 6. Network connectivity tests
print_header "🌐 Network Connectivity"

echo "Testing zrok API..."
if docker exec "$CONTAINER_NAME" sh -c 'wget -q --spider --timeout=5 https://api.zrok.io' 2>/dev/null; then
    print_success "Can reach zrok API (api.zrok.io)"
else
    print_error "Cannot reach zrok API"
fi

echo ""
echo "Testing target service (nginx-proxy)..."
TARGET=$(grep "^ZROK_TARGET_URL=" "$ENV_FILE" 2>/dev/null | cut -d'=' -f2 | tr -d '"' | tr -d "'")
if [ -n "$TARGET" ]; then
    TARGET_HOST=$(echo "$TARGET" | sed 's|http://||' | sed 's|https://||' | cut -d':' -f1)
    TARGET_PORT=$(echo "$TARGET" | grep -oP ':\K[0-9]+' || echo "80")
    
    if docker exec "$CONTAINER_NAME" sh -c "timeout 5 bash -c '</dev/tcp/${TARGET_HOST}/${TARGET_PORT}'" 2>/dev/null; then
        print_success "Can reach target service: $TARGET"
    else
        print_error "Cannot reach target service: $TARGET"
        print_info "Check if $TARGET_HOST is accessible from the container"
    fi
else
    print_warning "ZROK_TARGET_URL not configured"
fi

# 7. Extract current zrok URL
print_header "🔗 Current Zrok URL"

ZROK_URL=$(docker logs "$CONTAINER_NAME" 2>&1 | grep -oP 'https://[a-z0-9]+\.share\.zrok\.io' | tail -1)

if [ -n "$ZROK_URL" ]; then
    print_success "Found active zrok URL:"
    echo "           $ZROK_URL"
    
    # Test if it's accessible
    echo ""
    echo "Testing URL accessibility..."
    if curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$ZROK_URL" | grep -qE "200|302|301"; then
        print_success "URL is accessible (HTTP response received)"
    else
        print_warning "URL is not responding (may still be initializing)"
    fi
else
    print_error "No zrok URL found in logs"
    print_info "The container may still be initializing or failed to create a share"
fi

# 8. Compare with current WEBHOOK_URL
print_header "📡 Webhook Configuration"

CURRENT_WEBHOOK=$(grep "^WEBHOOK_URL=" "$ENV_FILE" 2>/dev/null | cut -d'=' -f2 || echo "")

echo "Current WEBHOOK_URL in .env:"
if [ -n "$CURRENT_WEBHOOK" ]; then
    echo "   $CURRENT_WEBHOOK"
    
    if [ -n "$ZROK_URL" ] && [ "$CURRENT_WEBHOOK" != "$ZROK_URL" ]; then
        print_warning "WEBHOOK_URL doesn't match current zrok URL!"
        echo ""
        echo "   Expected: $ZROK_URL"
        echo "   Actual:   $CURRENT_WEBHOOK"
    else
        print_success "WEBHOOK_URL matches zrok URL"
    fi
else
    print_warning "WEBHOOK_URL not set in .env"
fi

# 9. Diagnostic summary and recommendations
print_header "💡 Diagnostic Summary & Recommendations"

ISSUES_FOUND=0

if [ ${#MISSING_VARS[@]} -gt 0 ]; then
    ((ISSUES_FOUND++))
    print_error "Missing environment variables: ${MISSING_VARS[*]}"
    echo "   Fix: Add these variables to your .env file"
fi

if ! docker exec "$CONTAINER_NAME" test -f /home/zrok/.zrok/environment.json 2>/dev/null; then
    ((ISSUES_FOUND++))
    print_error "Zrok is not enabled"
    echo "   Fix: Run 'docker exec $CONTAINER_NAME zrok enable YOUR_TOKEN'"
fi

if [ -z "$ZROK_URL" ]; then
    ((ISSUES_FOUND++))
    print_error "No active zrok share found"
    echo "   Fix: Restart the container or check logs for errors"
fi

if [ "$STATUS" != "running" ]; then
    ((ISSUES_FOUND++))
    print_error "Container is not running"
    echo "   Fix: docker compose --profile zrok up -d"
fi

if [ $ISSUES_FOUND -eq 0 ]; then
    echo ""
    print_success "No critical issues found!"
    echo ""
    if [ -n "$ZROK_URL" ]; then
        echo "Your zrok tunnel is active at:"
        echo "   $ZROK_URL"
        echo ""
        echo "To update n8n with this URL:"
        echo "   ./start.sh"
        echo ""
        echo "Or manually:"
        echo "   1. Update WEBHOOK_URL in .env"
        echo "   2. docker compose restart n8n n8n-runner"
    fi
else
    echo ""
    print_warning "Found $ISSUES_FOUND issue(s) - see recommendations above"
fi

print_header "✅ Diagnostic Complete"

# Offer to fix automatically
if [ $ISSUES_FOUND -gt 0 ]; then
    echo ""
    echo "Would you like to attempt automatic fixes? (yes/no)"
    read -r AUTOFIX
    
    if [ "$AUTOFIX" = "yes" ]; then
        print_info "Attempting automatic fixes..."
        
        # Restart container if not running
        if [ "$STATUS" != "running" ]; then
            print_info "Restarting zrok container..."
            docker compose --profile zrok restart "$CONTAINER_NAME"
            sleep 10
        fi
        
        # Try to enable zrok if not enabled
        if ! docker exec "$CONTAINER_NAME" test -f /home/zrok/.zrok/environment.json 2>/dev/null; then
            if grep -q "^ZROK_AUTH_TOKEN=" "$ENV_FILE"; then
                TOKEN=$(grep "^ZROK_AUTH_TOKEN=" "$ENV_FILE" | cut -d'=' -f2 | tr -d '"' | tr -d "'")
                if [ -n "$TOKEN" ]; then
                    print_info "Enabling zrok..."
                    docker exec "$CONTAINER_NAME" zrok enable "$TOKEN"
                    sleep 5
                fi
            fi
        fi
        
        # Restart to apply fixes
        print_info "Restarting zrok to apply fixes..."
        docker compose --profile zrok restart "$CONTAINER_NAME"
        
        print_success "Automatic fixes applied. Run this script again to verify."
    fi
fi
