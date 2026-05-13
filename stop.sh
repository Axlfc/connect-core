#!/bin/bash
set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo ""
    echo "================================================"
    echo -e "${BLUE}$1${NC}"
    echo "================================================"
    echo ""
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# --- Environment Configuration ---
ENVIRONMENT="production"
COMPOSE_FILE="docker-compose.yml"
ENV_FILE=".env"
PREFIX=""
NETWORK_SUFFIX="demo"

# Parse arguments
REMOVE_VOLUMES=false
PROFILE="gpu-nvidia"
STOP_ALL=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --staging)
            ENVIRONMENT="staging"
            COMPOSE_FILE="docker-compose.staging.yml"
            ENV_FILE=".env.staging"
            PREFIX="staging-"
            NETWORK_SUFFIX="staging-demo"
            shift
            ;;
        --volumes|-v)
            REMOVE_VOLUMES=true
            shift
            ;;
        --cpu)
            PROFILE="cpu"
            shift
            ;;
        --gpu-amd)
            PROFILE="gpu-amd"
            shift
            ;;
        --all)
            STOP_ALL=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --staging       Stop the staging environment"
            echo "  -v, --volumes   Also remove volumes (⚠️  deletes all data!)"
            echo "  --cpu           Stop CPU profile services"
            echo "  --gpu-amd       Stop AMD GPU profile services"
            echo "  --all           Stop ALL services regardless of profile"
            echo "  -h, --help      Show this help"
            echo ""
            echo "Default: stops production gpu-nvidia profile"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

print_header "🛑 Stopping AI Stack ($ENVIRONMENT)"

if [ "$STOP_ALL" = true ]; then
    print_info "Stopping ALL services (all profiles)"
else
    print_info "Profile: $PROFILE"
fi

if [ "$REMOVE_VOLUMES" = true ]; then
    echo -e "${RED}⚠️  WARNING: This will DELETE ALL DATA for the '$ENVIRONMENT' environment!${NC}"
    echo ""
    echo "This includes databases, models, workflows, and all other persistent data."
    echo ""
    echo -n "Are you sure? (type 'yes' to confirm): "
    read -r CONFIRM
    
    if [ "$CONFIRM" != "yes" ]; then
        echo "Aborted."
        exit 0
    fi
    echo ""
fi

# Get project name before stopping
PROJECT_NAME=$(grep COMPOSE_PROJECT_NAME "$ENV_FILE" 2>/dev/null | cut -d '=' -f2 || echo "ai-stack-secure")

# ✅ FIXED: Stop zrok tunnel FIRST before stopping other services
echo "🛑 Stopping zrok tunnel..."
docker stop "${PREFIX}zrok-tunnel" 2>/dev/null || true
docker stop "${PREFIX}zrok-client" 2>/dev/null || true
docker rm "${PREFIX}zrok-tunnel" 2>/dev/null || true
docker rm "${PREFIX}zrok-client" 2>/dev/null || true
print_success "Zrok tunnel stopped"

# Stop services
echo "🛑 Stopping services..."
if [ "$STOP_ALL" = true ]; then
    # Stop all profiles
    if [ "$REMOVE_VOLUMES" = true ]; then
        docker compose -f "$COMPOSE_FILE" --profile gpu-nvidia --profile voice --profile voice-cpu --profile gpu-amd --profile cpu --profile zrok down -v --remove-orphans 2>&1 | grep -v "attribute \`version\` is obsolete" || true
    else
        docker compose -f "$COMPOSE_FILE" --profile gpu-nvidia --profile voice --profile voice-cpu --profile gpu-amd --profile cpu --profile zrok down --remove-orphans 2>&1 | grep -v "attribute \`version\` is obsolete" || true
    fi
else
    # Stop specific profile
    if [ "$REMOVE_VOLUMES" = true ]; then
        docker compose -f "$COMPOSE_FILE" --profile "$PROFILE" --profile voice --profile voice-cpu --profile zrok down -v --remove-orphans 2>&1 | grep -v "attribute \`version\` is obsolete" || true
    else
        docker compose -f "$COMPOSE_FILE" --profile "$PROFILE" --profile voice --profile voice-cpu --profile zrok down --remove-orphans 2>&1 | grep -v "attribute \`version\` is obsolete" || true
    fi
fi

if [ "$REMOVE_VOLUMES" = true ]; then
    print_success "Services stopped and volumes removed"
else
    print_success "Services stopped (data preserved)"
fi

# Clean orphaned containers
echo "🧹 Cleaning orphaned containers..."
docker rm -f $(docker ps -aq --filter "name=${PROJECT_NAME}") 2>/dev/null || true

# ✅ FIXED: More thorough cleanup of all possible container names
docker rm -f "${PREFIX}ollama-pull" "${PREFIX}zrok-config-temp" 2>/dev/null || true
docker rm -f "${PREFIX}whisper-stt" "${PREFIX}whisper-stt-cpu" "${PREFIX}kokoro-tts" "${PREFIX}kokoro-tts-cpu" "${PREFIX}voice-gateway" "${PREFIX}demucs" "${PREFIX}demucs-cpu" 2>/dev/null || true
docker rm -f "${PREFIX}forgejo" "${PREFIX}forgejo-db" "${PREFIX}forgejo-mcp" 2>/dev/null || true
docker rm -f "${PREFIX}n8n-runner" "${PREFIX}n8n-import" "${PREFIX}n8n" 2>/dev/null || true
docker rm -f "${PREFIX}libretranslate" "${PREFIX}languagetool" 2>/dev/null || true
docker rm -f "${PREFIX}comfyui" "${PREFIX}ollama-gpu" "${PREFIX}ollama-cpu" "${PREFIX}ollama-arm64" "${PREFIX}ollama-gpu-amd" 2>/dev/null || true
docker rm -f "${PREFIX}postgres" "${PREFIX}redis" "${PREFIX}qdrant" 2>/dev/null || true
docker rm -f "${PREFIX}matrix-synapse" "${PREFIX}matrix-postgres" 2>/dev/null || true
docker rm -f "${PREFIX}nginx-proxy" "${PREFIX}acme-companion" "${PREFIX}authelia" 2>/dev/null || true
docker rm -f "${PREFIX}fail2ban" "${PREFIX}duplicati" "${PREFIX}uptime-kuma" 2>/dev/null || true
docker rm -f "${PREFIX}ollama-proxy" "${PREFIX}ollama-metrics-proxy" 2>/dev/null || true

# ✅ FIXED: Make absolutely sure zrok is gone
docker rm -f zrok-tunnel zrok-client 2>/dev/null || true

print_success "Orphaned containers cleaned"

# Clean networks
echo "🧹 Cleaning networks..."
NETWORK_NAME="${PROJECT_NAME}_${NETWORK_SUFFIX}"
docker network rm "${NETWORK_NAME}" 2>/dev/null || true
docker network rm "${PROJECT_NAME}_frontend" 2>/dev/null || true
docker network rm "${PROJECT_NAME}_backend" 2>/dev/null || true
docker network rm "${PROJECT_NAME}_ai" 2>/dev/null || true
docker network rm "${PROJECT_NAME}_monitoring" 2>/dev/null || true
docker network prune -f > /dev/null 2>&1 || true

print_success "Networks cleaned"

print_header "✅ Shutdown Complete for $ENVIRONMENT environment"

if [ "$REMOVE_VOLUMES" = false ]; then
    echo "💾 Data has been preserved in Docker volumes."
    echo "To remove all data for this environment, run:"
    if [ "$ENVIRONMENT" = "staging" ]; then
        echo "  $0 --staging --volumes"
    else
        echo "  $0 --volumes"
    fi
else
    print_warning "All data for the '$ENVIRONMENT' environment has been permanently deleted."
fi

echo ""
print_info "To start again:"
echo "  ./start.sh                # Start production"
echo "  ./start.sh --staging      # Start staging"
echo "  ./start.sh --voice        # Start with voice services"
echo ""

# ✅ FIXED: Display helpful info about webhook URL
if [ -f "$ENV_FILE" ]; then
    CURRENT_WEBHOOK=$(grep "^WEBHOOK_URL=" "$ENV_FILE" 2>/dev/null | cut -d'=' -f2 || echo "")
    if [ -n "$CURRENT_WEBHOOK" ]; then
        echo "📝 Note: Your last webhook URL was:"
        echo "   $CURRENT_WEBHOOK"
        echo ""
        print_warning "Zrok will generate a NEW URL on next start!"
        echo "   The start.sh script will automatically update WEBHOOK_URL in .env"
        echo ""
    fi
fi

print_success "All systems stopped cleanly! 👋"