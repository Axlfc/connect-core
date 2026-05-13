#!/bin/bash
# n8n Task Runner Diagnostic & Fix Script
# This script diagnoses and fixes common n8n task runner issues

set -e

echo "========================================="
echo "n8n Task Runner Diagnostic Tool"
echo "========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if containers are running
echo "1. Checking container status..."
if docker ps --format '{{.Names}}' | grep -q "^n8n$"; then
    echo -e "${GREEN}✓${NC} n8n container is running"
else
    echo -e "${RED}✗${NC} n8n container is NOT running"
    exit 1
fi

if docker ps --format '{{.Names}}' | grep -q "^n8n-runner$"; then
    echo -e "${GREEN}✓${NC} n8n-runner container is running"
else
    echo -e "${RED}✗${NC} n8n-runner container is NOT running"
    echo "Starting n8n-runner..."
    docker compose up -d n8n-runner
fi

echo ""
echo "2. Checking network connectivity..."

# Test n8n to runner connectivity
if docker exec n8n ping -c 1 n8n-runner > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} n8n can ping n8n-runner"
else
    echo -e "${RED}✗${NC} n8n CANNOT ping n8n-runner"
fi

# Test runner to n8n connectivity
if docker exec n8n-runner wget -q --spider http://n8n:5679 2>&1; then
    echo -e "${GREEN}✓${NC} n8n-runner can reach n8n broker on port 5679"
else
    echo -e "${RED}✗${NC} n8n-runner CANNOT reach n8n broker on port 5679"
fi

echo ""
echo "3. Checking environment variables..."

# Check if auth token is set
N8N_TOKEN=$(docker exec n8n printenv N8N_RUNNERS_AUTH_TOKEN 2>/dev/null || echo "")
RUNNER_TOKEN=$(docker exec n8n-runner printenv N8N_RUNNERS_AUTH_TOKEN 2>/dev/null || echo "")

if [ -n "$N8N_TOKEN" ]; then
    echo -e "${GREEN}✓${NC} N8N_RUNNERS_AUTH_TOKEN is set in n8n"
else
    echo -e "${RED}✗${NC} N8N_RUNNERS_AUTH_TOKEN is NOT set in n8n"
fi

if [ -n "$RUNNER_TOKEN" ]; then
    echo -e "${GREEN}✓${NC} N8N_RUNNERS_AUTH_TOKEN is set in n8n-runner"
else
    echo -e "${RED}✗${NC} N8N_RUNNERS_AUTH_TOKEN is NOT set in n8n-runner"
fi

if [ "$N8N_TOKEN" == "$RUNNER_TOKEN" ] && [ -n "$N8N_TOKEN" ]; then
    echo -e "${GREEN}✓${NC} Auth tokens match"
else
    echo -e "${RED}✗${NC} Auth tokens DO NOT match or are empty"
fi

# Check timeout settings
N8N_TIMEOUT=$(docker exec n8n printenv N8N_RUNNERS_TASK_TIMEOUT 2>/dev/null || echo "60")
RUNNER_TIMEOUT=$(docker exec n8n-runner printenv N8N_RUNNERS_TASK_TIMEOUT 2>/dev/null || echo "60")

echo ""
echo "4. Checking timeout configuration..."
echo "   n8n timeout: ${N8N_TIMEOUT}s"
echo "   runner timeout: ${RUNNER_TIMEOUT}s"

if [ "$N8N_TIMEOUT" -lt 300 ]; then
    echo -e "${YELLOW}⚠${NC}  Warning: n8n timeout is less than 300s (recommended: 600s)"
fi

if [ "$RUNNER_TIMEOUT" -lt 300 ]; then
    echo -e "${YELLOW}⚠${NC}  Warning: runner timeout is less than 300s (recommended: 600s)"
fi

echo ""
echo "5. Checking recent logs for errors..."
echo "   Last 10 lines from n8n:"
docker logs n8n --tail 10 2>&1 | grep -E "(error|Error|ERROR|timeout|Timeout)" || echo "   No recent errors found"

echo ""
echo "   Last 10 lines from n8n-runner:"
docker logs n8n-runner --tail 10 2>&1 | grep -E "(error|Error|ERROR|timeout|Timeout)" || echo "   No recent errors found"

echo ""
echo "6. Testing health endpoints..."

# Test n8n health
if docker exec n8n wget -q --spider http://localhost:5678/healthz 2>&1; then
    echo -e "${GREEN}✓${NC} n8n health endpoint is responding"
else
    echo -e "${RED}✗${NC} n8n health endpoint is NOT responding"
fi

# Test runner health
if docker exec n8n-runner wget -q --spider http://localhost:5680/healthz 2>&1; then
    echo -e "${GREEN}✓${NC} n8n-runner health endpoint is responding"
else
    echo -e "${YELLOW}⚠${NC}  n8n-runner health endpoint is NOT responding (may not be critical)"
fi

echo ""
echo "========================================="
echo "RECOMMENDED ACTIONS:"
echo "========================================="
echo ""

if [ "$N8N_TIMEOUT" -lt 600 ] || [ "$RUNNER_TIMEOUT" -lt 600 ]; then
    echo -e "${YELLOW}1.${NC} Update timeout values to 600 seconds"
    echo "   Add to your .env file:"
    echo "   N8N_RUNNERS_TASK_TIMEOUT=600"
    echo ""
fi

if [ "$N8N_TOKEN" != "$RUNNER_TOKEN" ] || [ -z "$N8N_TOKEN" ]; then
    echo -e "${YELLOW}2.${NC} Ensure N8N_RUNNERS_AUTH_TOKEN is set and matches"
    echo "   Generate a new token:"
    echo "   openssl rand -base64 32"
    echo "   Add to .env: N8N_RUNNERS_AUTH_TOKEN=<your_token>"
    echo ""
fi

echo -e "${YELLOW}3.${NC} Restart both containers with updated configuration:"
echo "   docker compose restart n8n n8n-runner"
echo ""

echo -e "${YELLOW}4.${NC} Monitor logs for continued issues:"
echo "   docker logs n8n -f"
echo "   docker logs n8n-runner -f"
echo ""

echo "========================================="
echo "Quick fix command (applies recommended changes):"
echo "========================================="
echo ""
echo "To apply all fixes automatically, run:"
echo "  bash fix-n8n-runners.sh"
echo ""
