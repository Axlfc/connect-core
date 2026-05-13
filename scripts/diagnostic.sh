#!/bin/bash

echo "=== N8N Telegram Diagnostic ==="
echo ""

# Check n8n is running
echo "1. Checking n8n container status..."
docker compose ps n8n

echo ""
echo "2. Checking n8n user and permissions..."
docker compose exec n8n id
docker compose exec n8n ls -la /home/node/.n8n | head -10

echo ""
echo "3. Checking environment variables..."
docker compose exec n8n env | grep -E "WEBHOOK_URL|N8N_HOST|N8N_PROTOCOL|N8N_PORT"

echo ""
echo "4. Checking n8n is accessible..."
curl -I http://localhost:5678/healthz

echo ""
echo "5. Checking recent executions..."
docker compose exec n8n ls -lah /home/node/.n8n/executions 2>/dev/null || echo "No executions directory found"

echo ""
echo "6. Checking credentials..."
docker compose exec n8n ls -la /home/node/.n8n/credentials/ 2>/dev/null || echo "No credentials found"

echo ""
echo "7. Recent n8n logs (last 20 lines)..."
docker compose logs --tail=20 n8n

echo ""
echo "8. Checking for workflow errors..."
docker compose logs n8n | grep -i "error\|problem\|fail" | tail -10

echo ""
echo "=== Next Steps ==="
echo "1. If you see permission errors, run: sudo chown -R 1000:1000 ./n8n_storage"
echo "2. Make sure WEBHOOK_URL in .env matches your actual URL"
echo "3. Verify Telegram bot token is correct"
echo "4. Check workflow is activated in n8n UI"
echo "5. Test webhook with: curl https://api.telegram.org/botYOUR_TOKEN/getWebhookInfo"
