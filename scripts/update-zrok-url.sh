#!/bin/bash
set -e

echo "================================================"
echo "🚀 Zrok URL Update & n8n Restart Script"
echo "================================================"
echo ""

if ! command -v jq &> /dev/null; then
    echo "❌ ERROR: 'jq' is required but not installed."
    echo "   Install it with: sudo apt install jq  (Debian/Ubuntu)"
    exit 1
fi

# Check if zrok container is running
if ! docker ps | grep -q zrok-tunnel; then
    echo "❌ ERROR: zrok-tunnel container is not running"
    echo "   Start it with: docker compose up -d zrok-client"
    exit 1
fi

echo "⏳ Waiting for zrok tunnel to generate URL..."
MAX_WAIT=30
WAIT_COUNT=0

while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
    ZROK_TARGET_URL=$(docker logs zrok-tunnel 2>&1 | grep -oP 'https://[a-z0-9]+\.share\.zrok\.io' | tail -1)
    
    if [ -n "$ZROK_TARGET_URL" ]; then
        break
    fi
    
    echo "   Still waiting... ($WAIT_COUNT/$MAX_WAIT)"
    sleep 2
    WAIT_COUNT=$((WAIT_COUNT + 2))
done

if [ -z "$ZROK_TARGET_URL" ]; then
    echo ""
    echo "❌ ERROR: Could not extract zrok URL from logs after ${MAX_WAIT}s"
    echo ""
    echo "🔍 Recent zrok logs:"
    docker logs --tail 20 zrok-tunnel
    echo ""
    echo "💡 Try: docker compose restart zrok-client"
    exit 1
fi

echo "✅ Found zrok base URL: $ZROK_TARGET_URL"
echo ""

# Get the webhook path from n8n
echo "🔍 Getting webhook path from n8n..."
WEBHOOK_PATH=$(docker exec n8n n8n webhook:list 2>/dev/null | grep -oP '/webhook/[a-z0-9-]+/webhook' | head -1)

if [ -z "$WEBHOOK_PATH" ]; then
    echo "⚠️  WARNING: No active webhook found in n8n"
    echo "   Make sure your Telegram workflow is ACTIVE"
    echo "   Using base URL only..."
    FULL_WEBHOOK_URL="$ZROK_TARGET_URL"
else
    FULL_WEBHOOK_URL="${ZROK_TARGET_URL}${WEBHOOK_PATH}"
    echo "✅ Found webhook path: $WEBHOOK_PATH"
fi

echo "✅ Full webhook URL: $FULL_WEBHOOK_URL"
echo ""

# Check current WEBHOOK_URL
CURRENT_URL=$(grep "^WEBHOOK_URL=" .env 2>/dev/null | cut -d'=' -f2 || echo "")

if [ "$CURRENT_URL" = "$FULL_WEBHOOK_URL" ]; then
    echo "ℹ️  WEBHOOK_URL is already set to: $FULL_WEBHOOK_URL"
    echo "   No changes needed!"
fi

echo "📝 Updating .env file..."

# Backup .env with timestamp
BACKUP_FILE=".env.backup.$(date +%Y%m%d_%H%M%S)"
cp .env "$BACKUP_FILE"
echo "   Backup created: $BACKUP_FILE"

# Update or add WEBHOOK_URL
if grep -q "^WEBHOOK_URL=" .env; then
    # Update existing line
    sed -i "s|^WEBHOOK_URL=.*|WEBHOOK_URL=$FULL_WEBHOOK_URL|" .env
    echo "   ✅ Updated existing WEBHOOK_URL"
else
    # Add new line (should be after other n8n variables)
    echo "" >> .env
    echo "# Auto-updated by update-zrok-url.sh" >> .env
    echo "WEBHOOK_URL=$FULL_WEBHOOK_URL" >> .env
    echo "   ✅ Added new WEBHOOK_URL"
fi

# Show the change
echo ""
echo "📊 Change summary:"
echo "   Old: $CURRENT_URL"
echo "   New: $FULL_WEBHOOK_URL"
echo ""

# Restart n8n to pick up the new webhook URL
echo "🔄 Restarting n8n to apply changes..."
docker compose stop n8n
docker compose rm -f n8n
docker compose up -d n8n

# Para el runner
docker compose stop n8n-runner

# Levántalo de nuevo
docker compose up -d n8n-runner

# Wait for n8n to be ready
echo "⏳ Waiting for n8n to be ready..."
sleep 5

# Check if n8n is responding
if docker ps | grep -q "n8n"; then
    echo "   ✅ n8n container is running"
else
    echo "   ⚠️  Warning: n8n container may not be running properly"
fi

echo ""
echo "================================================"
echo "✅ Done!"
echo "================================================"
echo ""
echo "🌐 Access n8n at: $ZROK_TARGET_URL"
echo "📱 Full webhook URL: $FULL_WEBHOOK_URL"
echo ""

# Update Telegram webhook if bot token is available
if [ -f ".env" ]; then
    BOT_TOKEN=$(grep "^TELEGRAM_BOT_TOKEN=" .env 2>/dev/null | cut -d'=' -f2)
    
    if [ -n "$BOT_TOKEN" ] && [ -n "$WEBHOOK_PATH" ]; then
        echo "🤖 Updating Telegram webhook..."
        
        TELEGRAM_RESPONSE=$(curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook" \
          -H "Content-Type: application/json" \
          -d "{\"url\": \"${FULL_WEBHOOK_URL}\", \"drop_pending_updates\": true}")
        
        if echo "$TELEGRAM_RESPONSE" | jq -e '.ok == true' > /dev/null 2>&1; then
            echo "   ✅ Telegram webhook updated successfully!"
        else
            echo "   ⚠️  Failed to update Telegram webhook"
            echo "   Response: $(echo $TELEGRAM_RESPONSE | jq -r '.description')"
        fi
        
        echo ""
        echo "📊 Current Telegram webhook status:"
        curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo" | jq '{
          url: .result.url,
          pending: .result.pending_update_count,
          last_error: .result.last_error_message
        }'
    fi
fi

echo ""
echo "💡 Tips:"
echo "   - Test the webhook: curl -I $FULL_WEBHOOK_URL"
echo "   - Check n8n logs: docker logs -f n8n"
echo "   - Monitor zrok: docker logs -f zrok-tunnel"
echo ""