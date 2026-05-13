#!/bin/bash
set -e

# Colors for output
BLUE='\033[0;34m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

print_header() {
    echo -e "\n${BLUE}================================================${NC}"
    echo -e "${BLUE}🛑 $1${NC}"
    echo -e "${BLUE}================================================${NC}\n"
}

# Configuration
COMPOSE_FILE="docker-compose.yml"

print_header "Stopping Simplified Stack"

# We stop all profiles to ensure everything is cleaned up
docker compose -f "$COMPOSE_FILE" \
    --profile minimal \
    --profile minimal-nvidia \
    --profile minimal-amd \
    --profile minimal-cpu \
    --profile cms \
    --profile git \
    --profile knowledge \
    --profile creative-nvidia \
    --profile creative-amd \
    down --remove-orphans

echo -e "\n${GREEN}✅ Services stopped.${NC}"
