#!/bin/bash

# N8N Runners Diagnostic Script
# Checks the status and configuration of n8n task runners

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

print_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
print_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }
print_section() { echo -e "\n${BLUE}=== $1 ===${NC}"; }

echo "=================================================================="
print_info "N8N Runners Diagnostic Tool"
echo "=================================================================="

# 1. Container Status
print_section "1. Container Status"
docker compose ps n8n n8n-runner

# 2. Check if runners are registered with n8n
print_section "2. Registered Runners"
echo "Checking n8n logs for runner registration..."
docker compose logs n8n | grep -A 2 "Registered runner" | tail -20 || print_warn "No runners registered yet"

# 3. Check Python runner specifically
print_section "3. Python Runner Status"
echo "Checking for Python runner errors..."
docker compose logs n8n-runner | grep -E "launcher:py|runner:py" | tail -30

# 4. Check JavaScript runner
print_section "4. JavaScript Runner Status"
echo "Checking for JavaScript runner errors..."
docker compose logs n8n-runner | grep -E "launcher:js|runner:js" | tail -30

# 5. Verify websockets module
print_section "5. Verify Python Environment"
echo "Testing if websockets.asyncio is available..."
docker compose exec n8n-runner /home/runner/custom-venv/bin/python -c \
    "import websockets.asyncio; print('✅ websockets.asyncio is available')" 2>&1 || \
    print_error "websockets.asyncio NOT available - need to rebuild!"

# 6. Check broker connection
print_section "6. Task Broker Connection"
echo "Checking broker connectivity..."
docker compose logs n8n-runner | grep -E "(Task broker|Connected:|Disconnected:)" | tail -20

# 7. Check environment variables
print_section "7. Environment Variables"
echo "N8N_RUNNERS_TASK_BROKER_URI:"
docker compose exec n8n-runner sh -c 'echo $N8N_RUNNERS_TASK_BROKER_URI'
echo ""
echo "N8N_RUNNERS_AUTH_TOKEN (masked):"
docker compose exec n8n-runner sh -c 'echo ${N8N_RUNNERS_AUTH_TOKEN:0:10}...'

# 8. Network connectivity test
print_section "8. Network Connectivity"
echo "Testing connectivity from runner to n8n..."
docker compose exec n8n-runner wget -q --spider http://n8n:5679 && \
    print_info "✅ Can reach n8n:5679" || \
    print_error "❌ Cannot reach n8n:5679"

# 9. Health check status
print_section "9. Health Check Status"
docker compose ps n8n-runner --format "table {{.Name}}\t{{.Status}}"

# 10. Recent errors
print_section "10. Recent Errors (last 50 lines)"
docker compose logs --tail=50 n8n-runner | grep -E "ERROR|error|Error|ModuleNotFoundError|Failed" || \
    print_info "No recent errors found! ✅"

# Summary
print_section "Summary"
echo ""

# Check if websockets.asyncio works
WEBSOCKETS_OK=$(docker compose exec -T n8n-runner /home/runner/custom-venv/bin/python -c \
    "import websockets.asyncio; print('OK')" 2>/dev/null || echo "FAIL")

# Check if connected to broker
BROKER_CONNECTED=$(docker compose logs n8n-runner | grep -c "Connected: ws://n8n:5679" || echo "0")

# Check if runner is registered
RUNNER_REGISTERED=$(docker compose logs n8n | grep -c "Registered runner" || echo "0")

echo "Status Check:"
echo "-------------"
if [ "$WEBSOCKETS_OK" = "OK" ]; then
    print_info "✅ websockets.asyncio module: Available"
else
    print_error "❌ websockets.asyncio module: NOT AVAILABLE - Run rebuild script!"
fi

if [ "$BROKER_CONNECTED" -gt "0" ]; then
    print_info "✅ Task Broker Connection: Connected ($BROKER_CONNECTED times)"
else
    print_warn "⚠️  Task Broker Connection: Not detected"
fi

if [ "$RUNNER_REGISTERED" -gt "0" ]; then
    print_info "✅ Runner Registration: Registered ($RUNNER_REGISTERED runners)"
else
    print_warn "⚠️  Runner Registration: No runners registered"
fi

echo ""
echo "=================================================================="

if [ "$WEBSOCKETS_OK" != "OK" ]; then
    echo ""
    print_error "ACTION REQUIRED: Rebuild the runner image"
    echo ""
    echo "Run this command:"
    echo "  bash rebuild-runner.sh"
    echo ""
elif [ "$BROKER_CONNECTED" -eq "0" ]; then
    echo ""
    print_warn "Runners are built correctly but not connecting to broker"
    echo ""
    echo "Troubleshooting steps:"
    echo "1. Check n8n is running: docker compose ps n8n"
    echo "2. Restart runner: docker compose restart n8n-runner"
    echo "3. Check logs: docker compose logs -f n8n-runner"
    echo ""
else
    echo ""
    print_info "✅ Everything looks good!"
    echo ""
    echo "Your runners should be working. To verify:"
    echo "1. Go to n8n and create a workflow with a Code node"
    echo "2. The Code node should execute successfully"
    echo ""
fi
