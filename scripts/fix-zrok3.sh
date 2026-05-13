#!/bin/bash
set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }
print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }

echo ""
echo "========================================"
echo -e "${BLUE}🔧 Zrok Complete Reset & Fix${NC}"
echo "========================================"
echo ""

print_warning "This will:"
echo "  1. Stop and remove the zrok container"
echo "  2. Clean the .zrok directory completely"
echo "  3. Remove any reserved share configuration"
echo "  4. Start fresh with a new public share"
echo "  5. Update WEBHOOK_URL in .env"
echo "  6. Restart n8n with the new URL"
echo ""
echo "Press ENTER to continue or Ctrl+C to cancel..."
read

# Step 1: Stop the container
print_info "Step 1: Stopping zrok-tunnel container..."
docker compose --profile zrok stop zrok-tunnel 2>/dev/null || true
docker stop zrok-tunnel 2>/dev/null || true
sleep 2
print_success "Container stopped"

# Step 2: Remove the container
print_info "Step 2: Removing zrok-tunnel container..."
docker rm -f zrok-tunnel 2>/dev/null || true
print_success "Container removed"

# Step 3: Clean up the .zrok directory completely
print_info "Step 3: Cleaning .zrok directory..."
if [ -d ".zrok" ]; then
    # Always backup for safety
    BACKUP_DIR=".zrok.backup.$(date +%Y%m%d_%H%M%S)"
    if [ "$(ls -A .zrok 2>/dev/null)" ]; then
        mv .zrok "$BACKUP_DIR"
        print_info "Backed up existing .zrok to: $BACKUP_DIR"
    else
        rm -rf .zrok
    fi
fi

mkdir -p .zrok
chmod 755 .zrok
print_success "Fresh .zrok directory created"

# Step 4: Remove reserved share from .env
print_info "Step 4: Configuring for public share..."

if grep -q "^ZROK_RESERVED_SHARE=..*" .env 2>/dev/null; then
    # Backup .env
    BACKUP_ENV=".env.backup.$(date +%Y%m%d_%H%M%S)"
    cp .env "$BACKUP_ENV"
    print_info "Backed up .env to: $BACKUP_ENV"
    
    # Comment out or empty the reserved share
    sed -i 's/^ZROK_RESERVED_SHARE=.*/ZROK_RESERVED_SHARE=/' .env
    print_success "Removed reserved share configuration"
else
    print_success "Already configured for public share"
fi

# Step 5: Verify environment variables
print_info "Step 5: Verifying environment variables..."

if ! grep -q "^ZROK_AUTH_TOKEN=" .env; then
    print_error "ZROK_AUTH_TOKEN not found in .env"
    echo ""
    echo "Please add your zrok token to .env:"
    echo "  ZROK_AUTH_TOKEN=your-token-here"
    echo ""
    echo "Get your token from: https://zrok.io"
    exit 1
fi

TOKEN=$(grep "^ZROK_AUTH_TOKEN=" .env | cut -d'=' -f2 | tr -d '"' | tr -d "'" | xargs)
if [ -z "$TOKEN" ]; then
    print_error "ZROK_AUTH_TOKEN is empty in .env"
    exit 1
fi

print_success "ZROK_AUTH_TOKEN found: ${TOKEN:0:10}...${TOKEN: -4}"

# Verify other required variables
TARGET_URL=$(grep "^ZROK_TARGET_URL=" .env 2>/dev/null | cut -d'=' -f2 | tr -d '"' | tr -d "'" | xargs || echo "http://nginx-proxy:80")
API_ENDPOINT=$(grep "^ZROK_API_ENDPOINT=" .env 2>/dev/null | cut -d'=' -f2 | tr -d '"' | tr -d "'" | xargs || echo "https://api.zrok.io")

print_success "ZROK_API_ENDPOINT: $API_ENDPOINT"
print_success "ZROK_TARGET_URL: $TARGET_URL"

# Step 6: Create the improved entrypoint script
print_info "Step 6: Installing improved zrok entrypoint..."

mkdir -p scripts

cat > scripts/zrok-entrypoint.sh << 'ENTRYPOINT_EOF'
#!/bin/sh
# Improved zrok entrypoint with automatic environment reset
set -e

echo "=================================================="
echo "🚀 Zrok Tunnel Initialization"
echo "=================================================="

ZROK_ENV_DIR="${HOME}/.zrok"
ZROK_ENV_FILE="${ZROK_ENV_DIR}/environment.json"
ZROK_API_ENDPOINT="${ZROK_API_ENDPOINT:-https://api.zrok.io}"
ZROK_TARGET_URL="${ZROK_TARGET_URL:-http://nginx-proxy:80}"
ZROK_RESERVED_SHARE="${ZROK_RESERVED_SHARE:-}"

check_zrok_env() {
    if [ -f "${ZROK_ENV_FILE}" ]; then
        if zrok status >/dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

reset_zrok_env() {
    echo "🧹 Resetting zrok environment..."
    zrok disable 2>/dev/null || true
    rm -rf "${ZROK_ENV_DIR}"
    mkdir -p "${ZROK_ENV_DIR}"
    echo "✅ Environment reset complete"
}

enable_zrok() {
    echo "🔐 Enabling zrok with authentication token..."
    
    if [ -z "${ZROK_AUTH_TOKEN}" ]; then
        echo "❌ ERROR: ZROK_AUTH_TOKEN is not set!"
        exit 1
    fi
    
    if ! zrok enable "${ZROK_AUTH_TOKEN}" --headless; then
        echo "❌ Failed to enable zrok"
        return 1
    fi
    
    echo "✅ Zrok enabled successfully"
    return 0
}

create_zrok_share() {
    echo "🌐 Creating zrok share for ${ZROK_TARGET_URL}..."
    
    if [ -n "${ZROK_RESERVED_SHARE}" ]; then
        echo "ℹ️  Attempting reserved share: ${ZROK_RESERVED_SHARE}"
        
        if ! zrok share reserved "${ZROK_RESERVED_SHARE}" --headless; then
            echo "⚠️  Reserved share failed, falling back to public..."
            ZROK_RESERVED_SHARE=""
        else
            echo "✅ Reserved share started"
            return 0
        fi
    fi
    
    echo "🌍 Creating public share..."
    exec zrok share public "${ZROK_TARGET_URL}" --headless
}

main() {
    echo ""
    echo "📋 Configuration:"
    echo "   API Endpoint:    ${ZROK_API_ENDPOINT}"
    echo "   Target URL:      ${ZROK_TARGET_URL}"
    echo "   Reserved Share:  ${ZROK_RESERVED_SHARE:-<none - will create public>}"
    echo ""
    
    if check_zrok_env; then
        echo "✅ Zrok environment is valid"
    else
        echo "⚠️  Zrok environment invalid or missing"
        reset_zrok_env
        
        if ! enable_zrok; then
            echo "❌ Failed to enable zrok"
            exit 1
        fi
    fi
    
    echo ""
    echo "🔍 Verifying zrok status..."
    if ! zrok status; then
        echo "⚠️  Status check failed, resetting..."
        reset_zrok_env
        
        if ! enable_zrok; then
            echo "❌ Failed after reset"
            exit 1
        fi
    fi
    
    echo ""
    echo "📊 Environment Information:"
    zrok status
    
    echo ""
    create_zrok_share
}

main
ENTRYPOINT_EOF

chmod +x scripts/zrok-entrypoint.sh
print_success "Entrypoint script installed"

# Step 7: Start the container fresh
print_info "Step 7: Starting fresh zrok-tunnel container..."
docker compose --profile zrok up -d zrok-tunnel 2>&1 | grep -v "attribute.*obsolete" || true
sleep 5
print_success "Container started"

# Step 8: Wait for initialization and URL
print_info "Step 8: Waiting for zrok to create tunnel..."
MAX_WAIT=90
WAIT_COUNT=0
ZROK_URL=""

echo -n "⏳ Waiting for URL"
while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
    # Check if container is still running
    if ! docker ps --format '{{.Names}}' | grep -q "^zrok-tunnel$"; then
        echo ""
        print_error "Container stopped running"
        echo ""
        echo "📋 Recent logs:"
        docker logs zrok-tunnel 2>&1 | tail -30
        exit 1
    fi
    
    # Check for URL in logs
    ZROK_URL=$(docker logs zrok-tunnel 2>&1 | grep -oP 'https://[a-z0-9]+\.share\.zrok\.io' | tail -1)
    
    if [ -n "$ZROK_URL" ]; then
        echo ""
        break
    fi
    
    # Check for critical errors
    if docker logs zrok-tunnel 2>&1 | tail -10 | grep -qi "error.*unable to enable"; then
        echo ""
        print_error "Failed to enable zrok environment"
        docker logs zrok-tunnel 2>&1 | tail -30
        exit 1
    fi
    
    echo -n "."
    sleep 3
    WAIT_COUNT=$((WAIT_COUNT + 3))
done

echo ""

if [ -z "$ZROK_URL" ]; then
    print_error "No zrok URL found after ${MAX_WAIT}s"
    echo ""
    echo "📋 Full logs:"
    docker logs zrok-tunnel 2>&1
    exit 1
fi

print_success "Zrok tunnel is active!"
echo ""
echo "   🌐 URL: $ZROK_URL"
echo ""

# Step 9: Update .env with new URL
print_info "Step 9: Updating WEBHOOK_URL in .env..."

CURRENT_URL=$(grep "^WEBHOOK_URL=" .env 2>/dev/null | cut -d'=' -f2 || echo "")

# Backup .env if not already done
if [ ! -f ".env.backup.$(date +%Y%m%d)_latest" ]; then
    cp .env ".env.backup.$(date +%Y%m%d)_latest"
fi

# Update or add WEBHOOK_URL
if grep -q "^WEBHOOK_URL=" .env; then
    sed -i "s|^WEBHOOK_URL=.*|WEBHOOK_URL=$ZROK_URL|" .env
else
    echo "" >> .env
    echo "# Auto-updated by fix-zrok.sh on $(date)" >> .env
    echo "WEBHOOK_URL=$ZROK_URL" >> .env
fi

print_success "Updated WEBHOOK_URL"
echo "   Old: ${CURRENT_URL:-<not set>}"
echo "   New: $ZROK_URL"

# Step 10: Restart n8n to pick up new URL
print_info "Step 10: Restarting n8n services..."
docker compose stop n8n n8n-runner 2>&1 | grep -v "attribute.*obsolete" || true
sleep 3
docker compose up -d n8n n8n-runner 2>&1 | grep -v "attribute.*obsolete" || true
sleep 12

if docker ps --format '{{.Names}}' | grep -q "^n8n$"; then
    print_success "n8n restarted successfully"
    
    # Wait a bit more for n8n to initialize
    sleep 5
    
    # Check if n8n reports the correct URL
    N8N_URL=$(docker logs n8n 2>&1 | grep "Editor is now accessible" -A 1 | grep -oP 'https://[a-z0-9]+\.share\.zrok\.io' | tail -1)
    if [ -n "$N8N_URL" ]; then
        if [ "$N8N_URL" = "$ZROK_URL" ]; then
            print_success "n8n is using the correct URL: $N8N_URL"
        else
            print_warning "n8n URL mismatch: $N8N_URL (expected: $ZROK_URL)"
        fi
    fi
else
    print_warning "n8n may not have started properly"
fi

# Step 11: Final status
echo ""
echo "========================================"
echo -e "${GREEN}✅ Zrok Complete Fix Done!${NC}"
echo "========================================"
echo ""
echo "🌐 Your zrok tunnel URL:"
echo "   $ZROK_URL"
echo ""
echo "📋 Verification commands:"
echo "   docker logs -f zrok-tunnel     # Monitor zrok"
echo "   docker logs -f n8n             # Monitor n8n"
echo "   curl -I $ZROK_URL              # Test the URL"
echo ""

# Test the URL
print_info "Testing zrok URL accessibility..."
sleep 3
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$ZROK_URL" || echo "000")

if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 400 ]; then
    print_success "✅ URL is accessible (HTTP $HTTP_CODE)"
else
    print_warning "⚠️  URL test returned HTTP $HTTP_CODE"
    echo "   The tunnel may still be initializing, try again in a few seconds"
fi

echo ""
print_success "🎉 All done! Your tunnel is ready to use."
echo ""
print_info "💡 Note: This is a PUBLIC share - the URL will change on restart"
echo "   To get a persistent URL, create a reserved share at: https://zrok.io"
