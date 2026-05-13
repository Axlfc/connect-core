#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "\n${BLUE}================================================${NC}"
    echo -e "${BLUE}🚀 $1${NC}"
    echo -e "${BLUE}================================================${NC}\n"
}

print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }
print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }

# Configuration
COMPOSE_FILE="docker-compose.yml"
ENV_FILE=".env"

show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Hardware Options (Choose one):"
    echo "  --nvidia           Use NVIDIA GPU (default if none specified)"
    echo "  --cpu              Use CPU only"
    echo ""
    echo "Other Options:"
    echo "  --zrok             Enable zrok tunnel"
    echo "  -h, --help         Show this help message"
}

HW_PROFILE="gpu-nvidia"
VOICE_PROFILE="voice"
ZROK=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --nvidia) HW_PROFILE="gpu-nvidia"; VOICE_PROFILE="voice"; shift ;;
        --cpu)    HW_PROFILE="cpu"; VOICE_PROFILE="voice-cpu"; shift ;;
        --zrok)    ZROK=true; shift ;;
        -h|--help) show_help; exit 0 ;;
        *) print_error "Unknown option: $1"; show_help; exit 1 ;;
    esac
done

# Check for environment file
if [ ! -f "$ENV_FILE" ]; then
    print_warning "Environment file '$ENV_FILE' not found!"
    if [ -f "scripts/setup-env.sh" ]; then
        print_info "Running setup-env.sh..."
        bash scripts/setup-env.sh
    else
        print_error "Please create .env file (use .env.example as template) first."
        exit 1
    fi
fi

# Start services
print_header "Starting Very Simplified AI Stack"
print_info "Hardware: $HW_PROFILE"

COMPOSE_ARGS=("--profile" "$HW_PROFILE" "--profile" "$VOICE_PROFILE")
if [ "$ZROK" = true ]; then
    COMPOSE_ARGS+=("--profile" "zrok")
fi

docker compose -f "$COMPOSE_FILE" "${COMPOSE_ARGS[@]}" up -d

print_success "Services are starting!"
echo "Use 'docker compose ps' to check status."
