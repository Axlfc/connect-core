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
echo -e "${BLUE}🔧 Zrok Fix Script${NC}"
echo "========================================"
echo ""

print_warning "This will reset zrok configuration and restart the container"
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

# Step 3: Clean up the .zrok directory
print_info "Step 3: Cleaning .zrok directory..."
if [ -d ".zrok" ]; then
    # Backup if there's anything in it
    if [ "$(ls -A .zrok)" ]; then
        BACKUP_DIR=".zrok.backup.$(date +%Y%m%d_%H%M%S)"
        mv .zrok "$BACKUP_DIR"
        print_info "Backed up to: $BACKUP_DIR"
    else
        rm -rf .zrok
    fi
fi

mkdir -p .zrok
chmod 755 .zrok
print_success "Clean .zrok directory created"

# Step 4: Verify environment variables
print_info "Step 4: Verifying environment variables..."

if ! grep -q "^ZROK_AUTH_TOKEN=" .env; then
    print_error "ZROK_AUTH_TOKEN not found in .env"
    echo ""
    echo "Please add your zrok token to .env:"
    echo "  ZROK_AUTH_TOKEN=your-token-here"
    echo ""
    echo "Get your token from: https://zrok.io"
    exit 1
fi

TOKEN=$(grep "^ZROK_AUTH_TOKEN=" .env | cut -d'=' -f2 | tr -d '"' | tr -d "'")
if [ -z "$TOKEN" ]; then
    print_error "ZROK_AUTH_TOKEN is empty in .env"
    exit 1
fi

print_success "ZROK_AUTH_TOKEN found: ${TOKEN:0:10}...${TOKEN: -4}"

# Verify other required variables
for VAR in ZROK_API_ENDPOINT ZROK_TARGET_URL; do
    if grep -q "^${VAR}=" .env; then
        VALUE=$(grep "^${VAR}=" .env | cut -d'=' -f2)
        print_success "$VAR: $VALUE"
    else
        print_warning "$VAR not found in .env (will use defaults)"
    fi
done

# Step 5: Start the container fresh
print_info "Step 5: Starting fresh zrok-tunnel container..."
docker compose --profile zrok up -d zrok-tunnel 2>&1 | grep -v "attribute.*obsolete" || true
sleep 5
print_success "Container started"

# Step 6: Wait for initialization
print_info "Step 6: Waiting for zrok to initialize..."
MAX_WAIT=60
WAIT_COUNT=0

echo -n "⏳ Waiting"
while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
    # Check if container is still running
    if ! docker ps --format '{{.Names}}' | grep -q "^zrok-tunnel$"; then
        echo ""
        print_error "Container stopped running"
        echo ""
        echo "📋 Recent logs:"
        docker logs zrok-tunnel 2>&1 | tail -20
        exit 1
    fi
    
    # Check for URL in logs
    ZROK_URL=$(docker logs zrok-tunnel 2>&1 | grep -oP 'https://[a-z0-9]+\.share\.zrok\.io' | tail -1)
    
    if [ -n "$ZROK_URL" ]; then
        echo ""
        break
    fi
    
    # Check for errors
    if docker logs zrok-tunnel 2>&1 | tail -5 | grep -qi "error"; then
        echo ""
        print_error "Error detected in logs"
        docker logs zrok-tunnel 2>&1 | tail -20
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
echo "   URL: $ZROK_URL"
echo ""

# Step 7: Update .env with new URL
print_info "Step 7: Updating WEBHOOK_URL in .env..."

CURRENT_URL=$(grep "^WEBHOOK_URL=" .env 2>/dev/null | cut -d'=' -f2 || echo "")

if [ "$CURRENT_URL" != "$ZROK_URL" ]; then
    # Backup .env
    BACKUP_FILE=".env.backup.$(date +%Y%m%d_%H%M%S)"
    cp .env "$BACKUP_FILE"
    print_info "Backed up .env to: $BACKUP_FILE"
    
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
else
    print_success "WEBHOOK_URL already correct"
fi

# Step 8: Restart n8n to pick up new URL
print_info "Step 8: Restarting n8n to apply new webhook URL..."
docker compose stop n8n n8n-runner 2>&1 | grep -v "attribute.*obsolete" || true
sleep 3
docker compose up -d n8n n8n-runner 2>&1 | grep -v "attribute.*obsolete" || true
sleep 10

if docker ps --format '{{.Names}}' | grep -q "^n8n$"; then
    print_success "n8n restarted successfully"
else
    print_warning "n8n may not have started properly"
fi

# Step 9: Final status
echo ""
echo "========================================"
echo -e "${GREEN}✅ Zrok Fix Complete!${NC}"
echo "========================================"
echo ""
echo "🌐 Your zrok tunnel is now active at:"
echo "   $ZROK_URL"
echo ""
echo "📋 Verification commands:"
echo "   docker logs -f zrok-tunnel     # Monitor zrok"
echo "   docker logs -f n8n             # Monitor n8n"
echo "   curl -I $ZROK_URL              # Test the URL"
echo ""

# Test the URL
print_info "Testing zrok URL..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$ZROK_URL" || echo "000")

if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 400 ]; then
    print_success "URL is accessible (HTTP $HTTP_CODE)"
else
    print_warning "URL test returned HTTP $HTTP_CODE (may still be initializing)"
fi

echo ""
print_success "All done! 🎉"
