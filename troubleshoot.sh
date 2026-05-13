#!/bin/bash

# N8N Telegram Bot Troubleshooting & Fix Script
# This script diagnoses and fixes common n8n Telegram integration issues

set -e

echo "=== N8N Telegram Bot Fix Script ==="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
print_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
print_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 1. Fix n8n volume permissions
print_info "Step 1: Fixing n8n volume permissions..."

# Get the actual volume mount path
VOLUME_PATH=$(docker volume inspect n8n_storage --format '{{ .Mountpoint }}' 2>/dev/null || echo "")

if [ -z "$VOLUME_PATH" ]; then
    print_error "n8n_storage volume not found!"
    exit 1
fi

print_info "Volume path: $VOLUME_PATH"

# Fix permissions (requires sudo)
if [ "$EUID" -ne 0 ]; then 
    print_warn "This script needs sudo to fix volume permissions"
    print_info "Running: sudo chown -R 1000:1000 $VOLUME_PATH"
    sudo chown -R 1000:1000 "$VOLUME_PATH"
    sudo chmod -R 755 "$VOLUME_PATH"
else
    chown -R 1000:1000 "$VOLUME_PATH"
    chmod -R 755 "$VOLUME_PATH"
fi

print_info "Permissions fixed!"

# 2. Restart n8n container
print_info "Step 2: Restarting n8n container..."
docker compose restart n8n

# Wait for n8n to be ready
print_info "Waiting for n8n to be healthy..."
sleep 10

for i in {1..30}; do
    if docker compose exec -T n8n wget --spider -q http://localhost:5678/healthz 2>/dev/null; then
        print_info "n8n is healthy!"
        break
    fi
    if [ $i -eq 30 ]; then
        print_error "n8n failed to become healthy after 30 seconds"
        exit 1
    fi
    sleep 1
done

# 3. Verify webhook configuration
print_info "Step 3: Verifying webhook configuration..."

WEBHOOK_URL=$(docker compose exec -T n8n sh -c 'echo $WEBHOOK_URL' | tr -d '\r')
echo "Current WEBHOOK_URL: $WEBHOOK_URL"

if [ -z "$WEBHOOK_URL" ]; then
    print_error "WEBHOOK_URL is not set!"
    print_info "Please add this to your .env file:"
    echo "WEBHOOK_URL=https://your-domain.com"
    exit 1
fi

# 4. Check if Telegram workflow exists and is active
print_info "Step 4: Checking Telegram workflows..."

docker compose exec -T n8n n8n list:workflow 2>/dev/null || {
    print_warn "Could not list workflows. This is normal if no workflows exist yet."
}

# 5. Test webhook endpoint
print_info "Step 5: Testing webhook endpoint..."

if curl -s -o /dev/null -w "%{http_code}" "$WEBHOOK_URL/webhook-test" | grep -q "404\|200"; then
    print_info "Webhook endpoint is accessible!"
else
    print_warn "Webhook endpoint returned unexpected status. This might be normal if no webhook is configured."
fi

# 6. Display Telegram bot setup instructions
echo ""
echo "==================================================================="
print_info "TELEGRAM BOT SETUP INSTRUCTIONS"
echo "==================================================================="
echo ""
echo "1. Create a Telegram Bot (if you haven't already):"
echo "   - Message @BotFather on Telegram"
echo "   - Send: /newbot"
echo "   - Follow the instructions to get your BOT_TOKEN"
echo ""
echo "2. In n8n (${WEBHOOK_URL}):"
echo "   - Create a new workflow"
echo "   - Add a 'Telegram Trigger' node"
echo "   - In the Telegram Trigger node:"
echo "     • Create new credentials with your BOT_TOKEN"
echo "     • Select 'Updates' as the trigger type"
echo "   - Add your response logic (e.g., 'Send Message' node)"
echo "   - Activate the workflow (toggle in top-right)"
echo ""
echo "3. Set the webhook URL in Telegram:"
echo "   The webhook URL will be automatically set when you activate"
echo "   the workflow. It will look like:"
echo "   ${WEBHOOK_URL}/webhook/telegram-trigger-id"
echo ""
echo "4. Test your bot:"
echo "   - Open Telegram and message your bot"
echo "   - Check the execution log in n8n"
echo ""
echo "==================================================================="
print_info "TROUBLESHOOTING TIPS"
echo "==================================================================="
echo ""
echo "• View n8n logs:"
echo "  docker compose logs -f n8n"
echo ""
echo "• Check executions in n8n:"
echo "  Go to: ${WEBHOOK_URL}/executions"
echo ""
echo "• Verify webhook is set correctly:"
echo "  curl https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo"
echo ""
echo "• Common issues:"
echo "  - Bot token is incorrect"
echo "  - Workflow is not activated"
echo "  - Webhook URL is not publicly accessible"
echo "  - Firewall blocking incoming webhooks"
echo ""
echo "• If using zrok tunnel, ensure it's running:"
echo "  docker compose logs zrok-tunnel"
echo ""

# 7. Final status check
print_info "Step 6: Final status check..."

echo ""
echo "Container Status:"
docker compose ps n8n

echo ""
echo "Recent n8n logs (last 10 lines):"
docker compose logs --tail=10 n8n

echo ""
print_info "Fix script completed!"
print_info "Your n8n instance is ready at: $WEBHOOK_URL"
echo ""
