#!/bin/bash

# Simple N8N Permission Fix
# This script fixes n8n volume permissions using Docker (no sudo required)

set -e

echo "=== Simple N8N Permission Fix ==="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
print_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 1. Find the volume name
print_info "Step 1: Finding n8n volume..."

PROJECT_DIR=$(basename "$(pwd)")
VOLUME_NAME=""

# Try different possible volume names
for vol in "n8n_storage" "${PROJECT_DIR}_n8n_storage" "cognito-stack_n8n_storage" "ai-stack-secure_n8n_storage"; do
    if docker volume inspect "$vol" >/dev/null 2>&1; then
        VOLUME_NAME="$vol"
        print_info "Found volume: $VOLUME_NAME"
        break
    fi
done

if [ -z "$VOLUME_NAME" ]; then
    print_error "Could not find n8n volume!"
    echo ""
    echo "Available volumes with 'n8n':"
    docker volume ls | grep n8n || echo "  (none found)"
    echo ""
    echo "All volumes:"
    docker volume ls
    exit 1
fi

# 2. Fix permissions using Docker (no sudo needed!)
print_info "Step 2: Fixing permissions using Docker..."

docker run --rm \
    -v "$VOLUME_NAME:/data" \
    alpine \
    sh -c "chown -R 1000:1000 /data && chmod -R 755 /data && echo 'Permissions fixed!'"

print_info "Permissions updated successfully!"

# 3. Restart n8n
print_info "Step 3: Restarting n8n..."
docker compose restart n8n

# 4. Wait for health check
print_info "Step 4: Waiting for n8n to be healthy..."
sleep 5

for i in {1..30}; do
    if docker compose ps n8n | grep -q "healthy"; then
        print_info "n8n is healthy! ✅"
        break
    fi
    if [ $i -eq 30 ]; then
        print_warn "n8n health check timeout (this might be normal)"
    fi
    sleep 1
done

# 5. Check for errors
print_info "Step 5: Checking for errors..."
echo ""
echo "Recent n8n logs:"
docker compose logs --tail=20 n8n | grep -E "(error|Error|ERROR|Problem|problem)" || echo "No errors found! ✅"

# 6. Show status
echo ""
print_info "Step 6: Final status check..."
echo ""
echo "Container Status:"
docker compose ps n8n
echo ""

# Get webhook URL
WEBHOOK_URL=$(docker compose exec -T n8n sh -c 'echo $WEBHOOK_URL' 2>/dev/null | tr -d '\r' || echo "Not set")

echo "Webhook URL: $WEBHOOK_URL"
echo ""

# 7. Next steps
echo "=================================================================="
print_info "✅ FIX COMPLETED!"
echo "=================================================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Access n8n at: $WEBHOOK_URL"
echo "2. Create a new workflow"
echo "3. Add 'Telegram Trigger' node"
echo "4. Configure your bot token from @BotFather"
echo "5. Activate the workflow"
echo ""
echo "Need help? Check the logs:"
echo "   docker compose logs -f n8n"
echo ""
echo "View executions in n8n:"
echo "   $WEBHOOK_URL/executions"
echo ""
