#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo ""
    echo "================================================"
    echo -e "${BLUE}🚀 $1${NC}"
    echo "================================================"
    echo ""
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# --- Environment Configuration ---
ENVIRONMENT="production"
COMPOSE_FILE="docker-compose.yml"
ENV_FILE=".env"
PREFIX=""
NETWORK_SUFFIX="demo"

# Parse command line arguments
PROFILE="gpu-nvidia"
SKIP_CLEANUP=false
SKIP_ZROK=false
ENABLE_VOICE=false
ENABLE_FORGEJO=false
LEAN_MATRIX=false
CLEAN_ALL=false

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
        --cpu)
            PROFILE="cpu"
            shift
            ;;
        --gpu-amd)
            PROFILE="gpu-amd"
            shift
            ;;
        --arm64)
            PROFILE="arm64"
            shift
            ;;
        --apple-silicon)
            PROFILE="arm64"
            shift
            ;;
        --voice)
            ENABLE_VOICE=true
            shift
            ;;
        --forgejo)
            ENABLE_FORGEJO=true
            shift
            ;;
        --skip-cleanup)
            SKIP_CLEANUP=true
            shift
            ;;
        --skip-zrok)
            SKIP_ZROK=true
            shift
            ;;
        --clean-matrix)
            CLEAN_MATRIX=true
            shift
            ;;
        --clean-all)
            CLEAN_ALL=true
            shift
            ;;	
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --staging          Use the staging environment (docker-compose.staging.yml)"
            echo "  --cpu              Use CPU-only Ollama (default: gpu-nvidia)"
            echo "  --gpu-amd          Use AMD GPU Ollama"
            echo "  --arm64            Use ARM64/Apple Silicon (M1/M2/M3/M4)"
            echo "  --apple-silicon    Alias for --arm64"
            echo "  --voice            Enable voice services (Whisper + Kokoro)"
            echo "  --forgejo          Enable Forgejo Git service"
            echo "  --skip-cleanup     Skip initial cleanup"
            echo "  --skip-zrok        Skip zrok URL update"
            echo "  --clean-matrix     Remove Matrix data volumes before starting"
            echo "  --clean-all        Remove all persistent data volumes before starting"
            echo "  -h, --help         Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                                  # Production with GPU NVIDIA"
            echo "  $0 --staging --cpu --voice          # Staging with CPU and voice"
            echo "  $0 --arm64                          # Apple Silicon M1/M2/M3/M4"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Check for environment file
if [ ! -f "$ENV_FILE" ]; then
    print_error "Environment file '$ENV_FILE' not found!"
    print_info "Did you forget to create it? You can copy the example file."
    exit 1
fi

# Check for secrets directory
if [ ! -d "./secrets" ]; then
    print_error "Secrets directory './secrets' not found!"
    print_info "Please run 'bash scripts/generate-secrets.sh' to create the necessary secret files."
    exit 1
fi

# Build profile list
PROFILES="$PROFILE"
if [ "$ENABLE_VOICE" = true ]; then
    if [ "$PROFILE" = "cpu" ]; then
        PROFILES="$PROFILES,voice-cpu"
    else
        PROFILES="$PROFILES,voice"
    fi
fi

print_header "AI Stack Startup Script ($ENVIRONMENT)"
print_info "Main Profile: $PROFILE"
if [ "$ENABLE_VOICE" = true ]; then
    print_info "Voice Services: Enabled"
fi
if [ "$ENABLE_FORGEJO" = true ]; then
    print_info "Forgejo: Enabled"
fi
echo ""

# ============================================
# STEP 1: Cleanup
# ============================================
if [ "$SKIP_CLEANUP" = false ]; then
    print_header "Step 1: Cleanup Previous Instances ($ENVIRONMENT)"
    
    echo "🧹 Stopping all services..."
    docker compose -f "$COMPOSE_FILE" --profile "$PROFILE" down --remove-orphans 2>&1 | grep -v "attribute \`version\` is obsolete" || true
    
    echo "🧹 Removing orphaned containers..."
    PROJECT_NAME=$(grep COMPOSE_PROJECT_NAME "$ENV_FILE" | cut -d '=' -f2)
    docker rm -f $(docker ps -aq --filter "name=${PROJECT_NAME}") 2>/dev/null || true
    docker rm -f "${PREFIX}ollama-pull" "${PREFIX}zrok-config-temp" 2>/dev/null || true
    docker rm -f "${PREFIX}whisper-stt" "${PREFIX}whisper-stt-cpu" "${PREFIX}kokoro-tts" "${PREFIX}kokoro-tts-cpu" "${PREFIX}voice-gateway" 2>/dev/null || true
    docker rm -f "${PREFIX}forgejo" "${PREFIX}forgejo-db" 2>/dev/null || true
    docker rm -f "${PREFIX}dozzle" "${PREFIX}cadvisor" 2>/dev/null || true
    
    # ✅ FIXED: Stop and remove zrok tunnel properly
    echo "🧹 Stopping zrok tunnel..."
    docker stop "${PREFIX}zrok-tunnel" 2>/dev/null || true
    docker rm "${PREFIX}zrok-tunnel" 2>/dev/null || true
    
    echo "🧹 Cleaning up networks..."
    NETWORK_NAME="${PROJECT_NAME}_${NETWORK_SUFFIX}"
    docker network rm ${NETWORK_NAME} 2>/dev/null || true
    docker network prune -f > /dev/null 2>&1 || true
    
    # Handle data volume cleanup
    if [ "$CLEAN_MATRIX" = true ]; then
        print_warning "Removing Matrix data volumes..."
        docker volume rm "${PROJECT_NAME}_matrix_data" "${PROJECT_NAME}_matrix_postgres" 2>/dev/null || true
    fi

    if [ "$CLEAN_ALL" = true ]; then
        print_warning "Removing ALL persistent data volumes..."
        docker compose -f "$COMPOSE_FILE" down -v --remove-orphans 2>&1 | grep -v "attribute \`version\` is obsolete" || true
    fi
    
    print_success "Cleanup completed"
else
    print_info "Skipping cleanup (--skip-cleanup flag set)"
fi

# ============================================
# STEP 2: Start Services
# ============================================
print_header "Step 2: Starting Services ($ENVIRONMENT)"

echo "🚀 Checking logs folders"
mkdir -p ./logs/{n8n,n8n-runner,postgres,qdrant,ollama,redis,whisper-stt,kokoro-tts,forgejo,matrix-synapse,matrix-postgres,nginx}

echo "🚀 Starting docker compose with file '$COMPOSE_FILE' and profiles: $PROFILES"
if [ "$ENABLE_FORGEJO" = true ]; then
    docker compose -f "$COMPOSE_FILE" --profile "$PROFILE" $([ "$ENABLE_VOICE" = true ] && echo "--profile voice" || [ "$PROFILE" = "cpu" ] && [ "$ENABLE_VOICE" = true ] && echo "--profile voice-cpu") up -d "${PREFIX}forgejo" "${PREFIX}forgejo-db" 2>&1 | grep -v "attribute \`version\` is obsolete" || true
fi

docker compose -f "$COMPOSE_FILE" $(echo "$PROFILES" | sed 's/,/ --profile /g' | sed 's/^/--profile /') up -d 2>&1 | grep -v "attribute \`version\` is obsolete" || true

print_success "Services started"

# ============================================
# STEP 3: Wait for Services
# ============================================
print_header "Step 3: Waiting for Services to be Healthy ($ENVIRONMENT)"

wait_for_service() {
    local service=$1
    local max_wait=${2:-60}
    local count=0
    
    echo -n "⏳ Waiting for $service"
    
    while [ $count -lt $max_wait ]; do
        local status=$(docker inspect --format='{{.State.Health.Status}}' "$service" 2>/dev/null || echo "none")
        local state=$(docker inspect --format='{{.State.Status}}' "$service" 2>/dev/null || echo "none")
        
        if [ "$status" = "healthy" ] || [ "$state" = "running" ]; then
            echo ""
            print_success "$service is ready"
            return 0
        fi
        
        echo -n "."
        sleep 3
        count=$((count + 3))
    done
    
    echo ""
    print_warning "$service did not become healthy within ${max_wait}s"
    echo "   Status: $(docker inspect --format='{{.State.Status}}' "$service" 2>/dev/null || echo 'not found')"
    echo "   Health: $(docker inspect --format='{{.State.Health.Status}}' "$service" 2>/dev/null || echo 'no healthcheck')"
    return 1
}

# Wait for critical services
wait_for_service "${PREFIX}postgres" 60
wait_for_service "${PREFIX}redis" 30
wait_for_service "${PREFIX}qdrant" 30
wait_for_service "${PREFIX}libretranslate" 120
wait_for_service "${PREFIX}languagetool" 60

# Wait for Matrix services
echo ""
print_info "Waiting for Matrix services..."
wait_for_service "${PREFIX}matrix-postgres" 60
wait_for_service "${PREFIX}matrix-synapse" 90

# Check if Matrix is properly configured
if docker ps --format '{{.Names}}' | grep -q "^${PREFIX}matrix-synapse$"; then
    print_success "Matrix Synapse is running"
else
    print_warning "Matrix Synapse is not running"
fi

# Wait for Voice services if enabled
if [ "$ENABLE_VOICE" = true ]; then
    echo ""
    print_info "Waiting for Voice services..."
    
    if [ "$PROFILE" = "cpu" ]; then
        wait_for_service "${PREFIX}whisper-stt-cpu" 90
        wait_for_service "${PREFIX}kokoro-tts-cpu" 120
    else
        wait_for_service "${PREFIX}whisper-stt" 90
        wait_for_service "${PREFIX}kokoro-tts" 120
    fi
fi

# Wait for Forgejo if enabled
if [ "$ENABLE_FORGEJO" = true ]; then
    echo ""
    print_info "Waiting for Forgejo services..."
    wait_for_service "${PREFIX}forgejo-db" 60
    wait_for_service "${PREFIX}forgejo" 90
fi

# Wait for n8n
echo ""
echo "⏳ Waiting for n8n to initialize..."
sleep 10

if docker ps --format '{{.Names}}' | grep -q "^${PREFIX}n8n$"; then
    print_success "n8n is running"
    
    # Check for n8n-runner
    if docker ps --format '{{.Names}}' | grep -q "^${PREFIX}n8n-runner$"; then
        print_success "n8n Task Runner is running"
    else
        print_warning "n8n Task Runner is not running - attempting to start..."
        docker compose -f "$COMPOSE_FILE" up -d "${PREFIX}n8n-runner" 2>&1 | grep -v "attribute \`version\` is obsolete" || true
        sleep 5
        if docker ps --format '{{.Names}}' | grep -q "^${PREFIX}n8n-runner$"; then
            print_success "n8n Task Runner started successfully"
        else
            print_error "n8n Task Runner failed to start"
            docker logs "${PREFIX}n8n-runner" --tail 20
        fi
    fi
else
    print_error "n8n failed to start"
    echo ""
    echo "📋 n8n logs:"
    docker compose -f "$COMPOSE_FILE" logs --tail 50 "${PREFIX}n8n" 2>&1 | grep -v "attribute \`version\` is obsolete"
    exit 1
fi

# ============================================
# STEP 4: Check Zrok and Update Webhook
# ============================================
if [ "$SKIP_ZROK" = false ]; then
    print_header "Step 4: Configuring Zrok Tunnel & Webhook ($ENVIRONMENT)"
    
    # ✅ FIXED: Check for zrok-tunnel with correct container name
    if ! docker ps --format '{{.Names}}' | grep -q "^${PREFIX}zrok-tunnel$"; then
        print_warning "zrok-tunnel is not running"
        echo "   Starting zrok tunnel with profile..."
        # ✅ FIXED: Use --profile zrok and correct service name
        docker compose -f "$COMPOSE_FILE" --profile zrok up -d "${PREFIX}zrok-tunnel" 2>&1 | grep -v "attribute \`version\` is obsolete" || true
        sleep 10  # Give zrok more time to initialize
    else
        print_success "zrok-tunnel is already running"
    fi
    
    # ✅ FIXED: Better zrok URL detection with multiple retries and fallbacks
    echo "⏳ Waiting for zrok tunnel to generate URL..."
    MAX_WAIT=60
    WAIT_COUNT=0
    ZROK_URL=""
    
    while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
        # Try to get URL from logs - primary container name
        ZROK_URL=$(docker logs "${PREFIX}zrok-tunnel" 2>&1 | grep -oP 'https://[a-z0-9]+\.share\.zrok\.io' | tail -1 2>/dev/null || true)
        
        if [ -n "$ZROK_URL" ]; then
            break
        fi
        
        echo -n "."
        sleep 2
        WAIT_COUNT=$((WAIT_COUNT + 2))
    done
    echo ""
    
    if [ -z "$ZROK_URL" ]; then
        print_error "Could not extract zrok URL after ${MAX_WAIT}s"
        echo ""
        echo "📋 zrok-tunnel logs:"
        docker logs "${PREFIX}zrok-tunnel" 2>&1 | tail -30 || true
        print_warning "Skipping webhook URL update"
    else
        print_success "Found zrok URL: $ZROK_URL"
        
        # ✅ Get the URL that n8n is currently using
        echo "🔍 Checking n8n's current accessible URL..."
        sleep 3
        
        # Get URL from n8n logs
        N8N_CURRENT_URL=$(docker logs "${PREFIX}n8n" 2>&1 | grep "Editor is now accessible via:" -A 1 | grep -oP 'https://[a-z0-9]+\.share\.zrok\.io' | tail -1 || true)
        
        if [ -n "$N8N_CURRENT_URL" ]; then
            print_info "n8n currently reports URL: $N8N_CURRENT_URL"
            
            # ✅ Compare URLs - zrok generates NEW URLs on restart
            if [ "$ZROK_URL" != "$N8N_CURRENT_URL" ]; then
                print_warning "Zrok has a NEW URL: $ZROK_URL"
                print_warning "n8n still has OLD URL: $N8N_CURRENT_URL"
                print_info "Will update n8n to use the new zrok URL"
            else
                print_success "URLs match - no update needed"
            fi
        fi
        
        echo "🔍 Checking for active webhooks in n8n..."
        sleep 2
        
        WEBHOOK_PATH=$(docker exec "${PREFIX}n8n" n8n webhook:list 2>/dev/null | grep -oP '/webhook/[a-z0-9-]+' | head -1 || true)
        
        if [ -z "$WEBHOOK_PATH" ]; then
            FULL_WEBHOOK_URL="$ZROK_URL"
            print_info "No active webhook found - using base URL"
        else
            FULL_WEBHOOK_URL="${ZROK_URL}${WEBHOOK_PATH}"
            print_success "Webhook path: $WEBHOOK_PATH"
            print_info "Full webhook URL: $FULL_WEBHOOK_URL"
        fi
        
        # ✅ Check against current WEBHOOK_URL in .env
        CURRENT_URL=$(grep "^WEBHOOK_URL=" "$ENV_FILE" 2>/dev/null | cut -d'=' -f2 || echo "")
        
        if [ "$CURRENT_URL" != "$ZROK_URL" ]; then
            echo "🔧 Updating $ENV_FILE with current zrok URL..."
            
            BACKUP_FILE="${ENV_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
            cp "$ENV_FILE" "$BACKUP_FILE"
            print_info "Backup created at $BACKUP_FILE"
            
            if grep -q "^WEBHOOK_URL=" "$ENV_FILE"; then
                sed -i "s|^WEBHOOK_URL=.*|WEBHOOK_URL=$ZROK_URL|" "$ENV_FILE"
            else
                echo "" >> "$ENV_FILE"
                echo "# Auto-updated by start.sh on $(date)" >> "$ENV_FILE"
                echo "WEBHOOK_URL=$ZROK_URL" >> "$ENV_FILE"
            fi
            
            print_success "Updated WEBHOOK_URL in $ENV_FILE"
            echo "   Old URL: ${CURRENT_URL:-<not set>}"
            echo "   New URL: $ZROK_URL"
            
            echo "🔄 Reloading n8n to apply new webhook URL..."
            print_info "Stopping n8n and runner to reload environment..."
            docker compose -f "$COMPOSE_FILE" stop "${PREFIX}n8n" "${PREFIX}n8n-runner" 2>&1 | grep -v "attribute \`version\` is obsolete" || true
            sleep 3
            
            print_info "Starting n8n with new WEBHOOK_URL..."
            docker compose -f "$COMPOSE_FILE" up -d "${PREFIX}n8n" "${PREFIX}n8n-runner" 2>&1 | grep -v "attribute \`version\` is obsolete" || true
            sleep 15
            
            # ✅ Verify n8n restarted correctly and now shows the NEW URL
            if docker ps --format '{{.Names}}' | grep -q "^${PREFIX}n8n$"; then
                print_success "n8n started successfully with new URL"
                
                # Wait for n8n to fully initialize and display its URL
                echo -n "⏳ Waiting for n8n to initialize"
                for i in {1..10}; do
                    echo -n "."
                    sleep 2
                    NEW_N8N_URL=$(docker logs "${PREFIX}n8n" 2>&1 | grep "Editor is now accessible via:" -A 1 | grep -oP 'https://[a-z0-9]+\.share\.zrok\.io' | tail -1 || true)
                    if [ -n "$NEW_N8N_URL" ] && [ "$NEW_N8N_URL" = "$ZROK_URL" ]; then
                        break
                    fi
                done
                echo ""
                
                # Final verification
                if [ -n "$NEW_N8N_URL" ]; then
                    if [ "$NEW_N8N_URL" = "$ZROK_URL" ]; then
                        print_success "✅ n8n now reports correct URL: $NEW_N8N_URL"
                    else
                        print_warning "⚠️  n8n reports: $NEW_N8N_URL (expected: $ZROK_URL)"
                        print_warning "The WEBHOOK_URL in .env is correct, but n8n may need more time to initialize"
                        print_info "Try: docker compose restart ${PREFIX}n8n ${PREFIX}n8n-runner"
                    fi
                else
                    print_warning "Could not verify n8n's URL from logs"
                    print_info "Check manually: docker logs ${PREFIX}n8n | grep 'accessible via'"
                fi
                
                # Check runner status
                if docker ps --format '{{.Names}}' | grep -q "^${PREFIX}n8n-runner$"; then
                    print_success "n8n-runner is running"
                else
                    print_warning "n8n-runner is not running - attempting to start..."
                    docker compose -f "$COMPOSE_FILE" up -d "${PREFIX}n8n-runner" 2>&1 | grep -v "attribute \`version\` is obsolete" || true
                fi
            else
                print_error "n8n failed to start"
                docker logs "${PREFIX}n8n" --tail 30
            fi
        else
            print_success "WEBHOOK_URL is already up to date"
            print_info "Current URL: $CURRENT_URL"
        fi
        
        # ✅ Display final webhook information
        echo ""
        print_header "📡 Webhook Configuration"
        echo "   Zrok Tunnel URL:  $ZROK_URL"
        if [ -n "$WEBHOOK_PATH" ]; then
            echo "   Active Webhook:   $FULL_WEBHOOK_URL"
        else
            echo "   Active Webhook:   <none configured yet>"
            echo "   💡 Create a Telegram/webhook workflow in n8n to activate"
        fi
    fi
else
    print_info "Skipping zrok configuration (--skip-zrok flag set)"
fi

# ============================================
# STEP 5: Final Status
# ============================================
print_header "Step 5: System Status ($ENVIRONMENT)"

echo "📊 Service Status:"
docker compose -f "$COMPOSE_FILE" ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>&1 | grep -v "attribute \`version\` is obsolete"

echo ""
print_header "✅ Startup Complete for $ENVIRONMENT environment!"

# ✅ FIXED: Display access URLs properly
echo ""
echo "🌐 Access URLs:"
echo "   n8n Editor:       $(grep "^WEBHOOK_URL=" "$ENV_FILE" | cut -d'=' -f2)"
echo "   Local Services:"
echo "     - n8n:          http://localhost:5678"
echo "     - ComfyUI:      http://localhost:8188"
echo "     - Forgejo:      http://localhost:3002"
echo "     - Grafana:      http://localhost:3000 (if monitoring enabled)"

echo ""
echo "📖 Useful Commands:"
echo "   • View logs:      docker compose -f $COMPOSE_FILE logs -f [service]"
echo "   • Stop all:       ./stop.sh"
if [ "$ENVIRONMENT" = "staging" ]; then
    echo "   • Stop staging:   ./stop.sh --staging"
fi
echo "   • Shell access:   docker exec -it ${PREFIX}[service] sh"
echo ""

UNHEALTHY=$(docker ps --format '{{.Names}}' --filter "health=unhealthy" --filter "name=${PROJECT_NAME}")
if [ -n "$UNHEALTHY" ]; then
    print_warning "Some services are unhealthy:"
    echo "$UNHEALTHY" | while read service; do
        echo "   • $service"
    done
    echo ""
    echo "   Check logs: docker compose -f $COMPOSE_FILE logs [service-name]"
fi

print_success "All systems operational! 🎉"