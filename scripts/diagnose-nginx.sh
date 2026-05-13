#!/bin/bash
set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

print_header() {
    echo -e "\n${CYAN}═══════════════════════════════════════════════${NC}"
    echo -e "${CYAN}🔍 $1${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════${NC}\n"
}

print_subheader() {
    echo -e "\n${BLUE}── $1${NC}"
}

print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }
print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }

# Check if running
if ! docker ps | grep -q nginx-proxy; then
    print_error "nginx-proxy is not running!"
    echo "Start it with: docker compose up -d nginx-proxy"
    exit 1
fi

print_header "NGINX-PROXY DIAGNOSTIC TOOL"

# ============================================
# 1. Check Container Status
# ============================================
print_header "1. Container Status"

services=("nginx-proxy" "n8n" "comfyui" "authelia" "uptime-kuma" "forgejo")

for service in "${services[@]}"; do
    if docker ps --format '{{.Names}}' | grep -q "^${service}$"; then
        status=$(docker inspect --format='{{.State.Status}}' "$service")
        health=$(docker inspect --format='{{.State.Health.Status}}' "$service" 2>/dev/null || echo "no-healthcheck")
        
        if [ "$status" = "running" ] && [ "$health" != "unhealthy" ]; then
            print_success "$service: $status ($health)"
        else
            print_warning "$service: $status ($health)"
        fi
    else
        print_error "$service: NOT RUNNING"
    fi
done

# ============================================
# 2. Check VIRTUAL_HOST Variables
# ============================================
print_header "2. VIRTUAL_HOST Environment Variables"

for service in n8n comfyui authelia uptime-kuma forgejo; do
    if docker ps --format '{{.Names}}' | grep -q "^${service}$"; then
        print_subheader "$service"
        
        vhost=$(docker inspect "$service" | jq -r '.[0].Config.Env[]' 2>/dev/null | grep VIRTUAL_HOST || echo "NOT SET")
        vport=$(docker inspect "$service" | jq -r '.[0].Config.Env[]' 2>/dev/null | grep VIRTUAL_PORT || echo "NOT SET")
        
        if echo "$vhost" | grep -q "NOT SET"; then
            print_error "VIRTUAL_HOST: $vhost"
        else
            print_success "$vhost"
        fi
        
        if echo "$vport" | grep -q "NOT SET"; then
            print_error "VIRTUAL_PORT: $vport"
        else
            print_info "$vport"
        fi
    fi
done

# ============================================
# 3. Check nginx generated config
# ============================================
print_header "3. Nginx Generated Configuration"

print_subheader "Generated upstreams"
docker exec nginx-proxy cat /etc/nginx/conf.d/default.conf 2>/dev/null | grep -E "^upstream|server.*:.*;" | head -20 || print_error "Cannot read nginx config"

print_subheader "Virtual hosts configured"
docker exec nginx-proxy cat /etc/nginx/conf.d/default.conf 2>/dev/null | grep "server_name" | head -10 || print_error "Cannot read nginx config"

# ============================================
# 4. Check vhost.d files
# ============================================
print_header "4. Vhost.d Custom Configurations"

print_subheader "Files in /etc/nginx/vhost.d/"
docker exec nginx-proxy ls -lh /etc/nginx/vhost.d/ 2>/dev/null || print_warning "Cannot list vhost.d directory"

print_subheader "Content of default vhost config"
if docker exec nginx-proxy test -f /etc/nginx/vhost.d/default 2>/dev/null; then
    print_success "default vhost config exists"
    echo ""
    docker exec nginx-proxy head -20 /etc/nginx/vhost.d/default 2>/dev/null
else
    print_error "No default vhost config found!"
fi

print_subheader "Content of n8n.localhost vhost config"
if docker exec nginx-proxy test -f /etc/nginx/vhost.d/n8n.localhost 2>/dev/null; then
    print_success "n8n.localhost vhost config exists"
    echo ""
    docker exec nginx-proxy head -20 /etc/nginx/vhost.d/n8n.localhost 2>/dev/null
else
    print_warning "No n8n.localhost vhost config found"
fi

# ============================================
# 5. Check Network Connectivity
# ============================================
print_header "5. Network Connectivity"

print_subheader "Networks"
for service in nginx-proxy n8n comfyui authelia; do
    if docker ps --format '{{.Names}}' | grep -q "^${service}$"; then
        networks=$(docker inspect "$service" | jq -r '.[0].NetworkSettings.Networks | keys[]' 2>/dev/null || echo "ERROR")
        print_info "$service: $networks"
    fi
done

print_subheader "Can nginx-proxy reach services?"
for service in n8n:5678 comfyui:8188 authelia:9091; do
    name=$(echo $service | cut -d: -f1)
    port=$(echo $service | cut -d: -f2)
    
    if docker exec nginx-proxy timeout 2 sh -c "nc -zv $name $port" 2>&1 | grep -q "succeeded"; then
        print_success "nginx-proxy → $service: ✓"
    else
        print_error "nginx-proxy → $service: ✗ (cannot connect)"
    fi
done

# ============================================
# 6. Check Authelia
# ============================================
print_header "6. Authelia Configuration"

if docker ps --format '{{.Names}}' | grep -q "^authelia$"; then
    print_subheader "Authelia health"
    if docker exec authelia wget -qO- http://localhost:9091/api/health 2>/dev/null; then
        print_success "Authelia API is responding"
    else
        print_error "Authelia API is not responding"
    fi
    
    print_subheader "Authelia configuration file"
    if docker exec authelia test -f /config/configuration.yml; then
        print_success "configuration.yml exists"
        docker exec authelia grep -E "^  domain:|^    - domain:" /config/configuration.yml 2>/dev/null | head -10
    else
        print_error "configuration.yml not found!"
    fi
    
    print_subheader "Authelia users database"
    if docker exec authelia test -f /config/users_database.yml; then
        print_success "users_database.yml exists"
    else
        print_error "users_database.yml not found!"
    fi
else
    print_error "Authelia is not running"
fi

# ============================================
# 7. Test HTTP Requests
# ============================================
print_header "7. HTTP Request Tests"

test_url() {
    local url=$1
    local name=$2
    
    response=$(docker exec nginx-proxy wget -qO- --timeout=5 "$url" 2>&1 || echo "FAILED")
    
    if echo "$response" | grep -qi "authelia\|login\|sign in"; then
        print_success "$name → Redirects to Authelia ✓"
    elif echo "$response" | grep -qi "welcome to nginx"; then
        print_warning "$name → Shows nginx welcome page (PROBLEM!)"
    elif echo "$response" | grep -qi "502\|503\|504"; then
        print_error "$name → Gateway error"
    elif echo "$response" | grep -qi "FAILED"; then
        print_error "$name → Connection failed"
    else
        print_info "$name → Got response (check manually)"
    fi
}

test_url "http://n8n.localhost" "n8n.localhost"
test_url "http://comfyui.localhost" "comfyui.localhost"
test_url "http://auth.localhost" "auth.localhost"
test_url "http://status.localhost" "status.localhost"

# ============================================
# 8. Check Docker Compose Configuration
# ============================================
print_header "8. Docker Compose Configuration Check"

print_subheader "Checking nginx-proxy volumes in docker-compose.yml"
if grep -A 10 "nginx-proxy:" docker-compose.yml | grep -q "./nginx-proxy/vhost.d:/etc/nginx/vhost.d"; then
    print_success "vhost.d volume mount is configured"
else
    print_error "vhost.d volume mount is MISSING or incorrect!"
    echo ""
    echo "Add this to nginx-proxy volumes:"
    echo "  - ./nginx-proxy/vhost.d:/etc/nginx/vhost.d:ro"
fi

print_subheader "Checking if vhost.d directory exists on host"
if [ -d "./nginx-proxy/vhost.d" ]; then
    print_success "./nginx-proxy/vhost.d exists"
    echo "Files:"
    ls -lh ./nginx-proxy/vhost.d/ 2>/dev/null || echo "  (empty)"
else
    print_error "./nginx-proxy/vhost.d does NOT exist!"
fi

# ============================================
# 9. Recent Logs
# ============================================
print_header "9. Recent Container Logs (last 10 lines)"

print_subheader "nginx-proxy logs"
docker logs nginx-proxy --tail 10 2>&1 | grep -v "attribute \`version\`"

print_subheader "authelia logs"
docker logs authelia --tail 10 2>&1 | grep -v "attribute \`version\`" || print_warning "Authelia not running"

print_subheader "n8n logs"
docker logs n8n --tail 10 2>&1 | grep -v "attribute \`version\`" || print_warning "n8n not running"

# ============================================
# 10. Summary & Recommendations
# ============================================
print_header "10. Summary & Recommended Actions"

issues_found=0

# Check critical issues
if ! docker exec nginx-proxy test -f /etc/nginx/vhost.d/default 2>/dev/null; then
    print_error "Issue #1: Missing default vhost configuration"
    echo "   Fix: Run ./fix-nginx-proxy.sh"
    echo ""
    issues_found=$((issues_found + 1))
fi

if ! grep -q "./nginx-proxy/vhost.d:/etc/nginx/vhost.d" docker-compose.yml; then
    print_error "Issue #2: vhost.d not mounted in docker-compose.yml"
    echo "   Fix: Update nginx-proxy volumes in docker-compose.yml"
    echo ""
    issues_found=$((issues_found + 1))
fi

if ! docker ps | grep -q authelia; then
    print_error "Issue #3: Authelia is not running"
    echo "   Fix: docker compose up -d authelia"
    echo ""
    issues_found=$((issues_found + 1))
fi

# Check if VIRTUAL_HOST is missing
for service in n8n comfyui; do
    if docker ps --format '{{.Names}}' | grep -q "^${service}$"; then
        if ! docker inspect "$service" | jq -r '.[0].Config.Env[]' 2>/dev/null | grep -q "VIRTUAL_HOST"; then
            print_error "Issue: $service missing VIRTUAL_HOST environment variable"
            echo "   Fix: Add to docker-compose.yml under $service:"
            echo "     environment:"
            echo "       - VIRTUAL_HOST=${service}.localhost"
            echo "       - VIRTUAL_PORT=<port>"
            echo ""
            issues_found=$((issues_found + 1))
        fi
    fi
done

if [ $issues_found -eq 0 ]; then
    print_success "No critical issues found!"
    echo ""
    echo "If services still show nginx welcome page:"
    echo "  1. Restart nginx-proxy: docker compose restart nginx-proxy"
    echo "  2. Wait 10 seconds for config regeneration"
    echo "  3. Test again: curl -v http://n8n.localhost"
else
    print_warning "Found $issues_found issue(s) - please fix them and restart services"
    echo ""
    echo "After fixing:"
    echo "  docker compose down"
    echo "  docker compose --profile gpu-nvidia up -d"
fi

print_header "Diagnostic Complete"
