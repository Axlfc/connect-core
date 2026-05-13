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

# Profiles to activate
PROFILES=()
HW_PROFILE=""
MINIMAL=false

show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Hardware Options (Choose one):"
    echo "  --nvidia           Use NVIDIA GPU (default if none specified)"
    echo "  --amd              Use AMD GPU"
    echo "  --cpu              Use CPU only"
    echo ""
    echo "Service Groups (Can be combined):"
    echo "  --minimal          Base AI (n8n, runners, qdrant, postgres, redis, ollama)"
    echo "  --cms              Orchestration (Drupal)"
    echo "  --git              Code hosting (Forgejo)"
    echo "  --knowledge        Knowledge base (Obsidian)"
    echo "  --creative         Image generation (ComfyUI)"
    echo "  --all              Start all services"
    echo ""
    echo "Other Options:"
    echo "  -h, --help         Show this help message"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --nvidia) HW_PROFILE="nvidia"; shift ;;
        --amd)    HW_PROFILE="amd"; shift ;;
        --cpu)    HW_PROFILE="cpu"; shift ;;
        --minimal) MINIMAL=true; shift ;;
        --cms)     PROFILES+=("cms"); shift ;;
        --git)     PROFILES+=("git"); shift ;;
        --knowledge) PROFILES+=("knowledge"); shift ;;
        --creative)  PROFILES+=("creative"); shift ;;
        --all)
            MINIMAL=true
            PROFILES+=("cms" "git" "knowledge" "creative")
            shift
            ;;
        -h|--help) show_help; exit 0 ;;
        *) print_error "Unknown option: $1"; show_help; exit 1 ;;
    esac
done

# Default hardware if none specified
if [ -z "$HW_PROFILE" ]; then
    print_info "No hardware profile specified, defaulting to --nvidia"
    HW_PROFILE="nvidia"
fi

# Ensure minimal is included if any extension is requested
if [ ${#PROFILES[@]} -gt 0 ]; then
    MINIMAL=true
fi

# Map selections to Docker Compose profiles
FINAL_PROFILES=()

if [ "$MINIMAL" = true ]; then
    FINAL_PROFILES+=("minimal")
    FINAL_PROFILES+=("minimal-$HW_PROFILE")
fi

for p in "${PROFILES[@]}"; do
    if [ "$p" == "creative" ]; then
        FINAL_PROFILES+=("creative-$HW_PROFILE")
    else
        FINAL_PROFILES+=("$p")
    fi
done

# Check for environment file
if [ ! -f "$ENV_FILE" ]; then
    print_warning "Environment file '$ENV_FILE' not found!"
    if [ -f "scripts/setup-env.sh" ]; then
        print_info "Running setup-env.sh..."
        bash scripts/setup-env.sh
    else
        print_error "Please create .env file first."
        exit 1
    fi
fi

# Start services
print_header "Starting Simplified Stack"
print_info "Hardware: $HW_PROFILE"
print_info "Profiles: ${FINAL_PROFILES[*]}"

COMPOSE_ARGS=()
for p in "${FINAL_PROFILES[@]}"; do
    COMPOSE_ARGS+=("--profile" "$p")
done

docker compose -f "$COMPOSE_FILE" "${COMPOSE_ARGS[@]}" up -d

print_success "Services are starting!"
echo "Use 'docker compose ps' to check status."
