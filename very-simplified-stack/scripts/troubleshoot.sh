#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}================================================"
echo "🔍 Troubleshooting Simplified Stack"
echo -e "================================================${NC}"

# Check Docker status
echo -e "\n${BLUE}📊 Container Status:${NC}"
docker compose ps

# Check unhealthy containers
UNHEALTHY=$(docker ps -a --filter "health=unhealthy" --format "{{.Names}}")
if [ -n "$UNHEALTHY" ]; then
    echo -e "\n${RED}⚠️  Found unhealthy containers:${NC}"
    echo "$UNHEALTHY"
    for container in $UNHEALTHY; do
        echo -e "\n${YELLOW}📋 Last 20 logs for $container:${NC}"
        docker logs --tail 20 "$container"
    done
else
    echo -e "\n${GREEN}✅ No unhealthy containers found.${NC}"
fi

# Check essential ports
echo -e "\n${BLUE}🔌 Checking Port Availability:${NC}"
check_port() {
    local name=$1
    local port=$2
    if command -v nc >/dev/null 2>&1; then
        if nc -z localhost "$port" >/dev/null 2>&1; then
            echo -e "${GREEN}✅ $name ($port) is open${NC}"
        else
            echo -e "${RED}❌ $name ($port) is CLOSED${NC}"
        fi
    else
        echo -e "${YELLOW}ℹ️  nc (netcat) not found, skipping port check for $name ($port)${NC}"
    fi
}

check_port "Qdrant" 6333
check_port "Ollama" 11434
check_port "Forgejo" 3002
check_port "Cognito Backend" 8000

# Check Disk Space
echo -e "\n${BLUE}💾 Disk Space Info:${NC}"
df -h ./data | tail -1

echo -e "\n${BLUE}================================================"
echo "✅ Troubleshooting report complete"
echo -e "================================================${NC}"
