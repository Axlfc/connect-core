#!/bin/bash
# Automated n8n Task Runner Fix Script
# This script applies fixes for timeout and permission issues

set -e

echo "========================================="
echo "n8n Task Runner Auto-Fix"
echo "========================================="
echo ""

# Backup .env file
if [ -f .env ]; then
    cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
    echo "✓ Backed up .env file"
fi

# Check if .env exists
if [ ! -f .env ]; then
    echo "Error: .env file not found"
    exit 1
fi

echo "Applying fixes to .env..."

# Function to update or add env variable
update_env_var() {
    local key=$1
    local value=$2
    local file=".env"
    
    if grep -q "^${key}=" "$file"; then
        # Update existing
        sed -i "s|^${key}=.*|${key}=${value}|" "$file"
        echo "  Updated: ${key}=${value}"
    else
        # Add new
        echo "${key}=${value}" >> "$file"
        echo "  Added: ${key}=${value}"
    fi
}

# Apply fixes
echo ""
echo "1. Increasing task timeout to 600 seconds..."
update_env_var "N8N_RUNNERS_TASK_TIMEOUT" "600"
update_env_var "EXECUTIONS_TIMEOUT" "600"
update_env_var "EXECUTIONS_TIMEOUT_MAX" "3600"

echo ""
echo "2. Ensuring runner configuration..."
update_env_var "N8N_RUNNERS_ENABLED" "true"
update_env_var "N8N_RUNNERS_MODE" "external"
update_env_var "N8N_RUNNERS_MAX_CONCURRENCY" "5"

echo ""
echo "3. Checking auth token..."
if ! grep -q "^N8N_RUNNERS_AUTH_TOKEN=" .env || [ -z "$(grep '^N8N_RUNNERS_AUTH_TOKEN=' .env | cut -d'=' -f2)" ]; then
    echo "  Generating new auth token..."
    NEW_TOKEN=$(openssl rand -base64 32)
    update_env_var "N8N_RUNNERS_AUTH_TOKEN" "$NEW_TOKEN"
    echo "  ⚠ IMPORTANT: New auth token generated. Save this!"
else
    echo "  Auth token already set"
fi

echo ""
echo "4. Setting broker configuration..."
update_env_var "N8N_RUNNERS_BROKER_LISTEN_ADDRESS" "0.0.0.0"
update_env_var "N8N_RUNNERS_BROKER_PORT" "5679"
update_env_var "N8N_RUNNERS_N8N_URI" "http://n8n:5678"

echo ""
echo "========================================="
echo "Fixes applied successfully!"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Restart the containers:"
echo "   docker compose restart n8n n8n-runner"
echo ""
echo "2. Monitor the logs:"
echo "   docker logs n8n -f"
echo ""
echo "3. Check for 'Registered runner' messages in logs"
echo ""
echo "If issues persist, check permissions:"
echo "   docker exec n8n ls -la /home/node/.n8n"
echo ""

# Ask user if they want to restart now
read -p "Do you want to restart n8n and n8n-runner now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "Restarting containers..."
    docker compose restart n8n n8n-runner
    echo ""
    echo "Waiting for services to stabilize (30 seconds)..."
    sleep 30
    echo ""
    echo "Checking logs..."
    docker logs n8n --tail 20
    echo ""
    echo "Check above for 'Registered runner' messages"
    echo "If you see them, the fix was successful!"
fi
