#!/bin/bash
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }
print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }

echo -e "${BLUE}🔧 Fixing nginx-proxy permissions issue${NC}"
echo ""

# 1. Check current configuration
print_info "Checking current docker-compose.yml..."
if grep -A 10 "nginx-proxy:" docker-compose.yml | grep "confd:/etc/nginx/conf.d:ro"; then
    print_error "Found the problem: confd is mounted as read-only (:ro)"
    echo ""
    echo "This prevents nginx-proxy from generating configuration files."
    echo ""
fi

# 2. Fix the docker-compose.yml
print_info "Creating backup of docker-compose.yml..."
cp docker-compose.yml docker-compose.yml.backup.$(date +%Y%m%d_%H%M%S)

print_info "Fixing nginx-proxy volumes..."
# Remove :ro from confd volume
sed -i 's|confd:/etc/nginx/conf.d:ro|confd:/etc/nginx/conf.d|g' docker-compose.yml

print_success "docker-compose.yml updated"

# 3. Verify the change
if grep -A 10 "nginx-proxy:" docker-compose.yml | grep "confd:/etc/nginx/conf.d" | grep -v ":ro"; then
    print_success "Volume mount is now writable"
else
    print_error "Fix failed - please check docker-compose.yml manually"
    exit 1
fi

# 4. Restart nginx-proxy
print_info "Stopping nginx-proxy..."
docker compose stop nginx-proxy

print_info "Removing old configuration volume..."
docker volume rm $(docker volume ls -q | grep confd) 2>/dev/null || true

print_info "Starting nginx-proxy..."
docker compose up -d nginx-proxy

print_info "Waiting for nginx-proxy to generate config..."
sleep 10

# 5. Check if config was generated
print_info "Checking if configuration was generated..."
if docker exec nginx-proxy test -f /etc/nginx/conf.d/default.conf; then
    print_success "Configuration file exists!"
    
    # Check if it has upstream definitions
    if docker exec nginx-proxy grep -q "upstream" /etc/nginx/conf.d/default.conf 2>/dev/null; then
        print_success "Upstream definitions found!"
        
        echo ""
        echo "Found upstreams:"
        docker exec nginx-proxy grep "^upstream" /etc/nginx/conf.d/default.conf
    else
        print_error "No upstream definitions found"
        echo ""
        echo "This means nginx-proxy is not detecting your services."
        echo "Check that services have VIRTUAL_HOST and VIRTUAL_PORT set."
    fi
else
    print_error "Configuration file was not generated"
    echo ""
    echo "Check logs:"
    echo "docker compose logs nginx-proxy --tail 50"
fi

# 6. Test
echo ""
print_info "Testing services..."

test_service() {
    local host=$1
    echo -n "  Testing $host... "
    
    response=$(curl -s -H "Host: $host" http://localhost/ 2>&1 | head -10)
    
    if echo "$response" | grep -qi "nginx.*welcome"; then
        echo -e "${RED}✗ Still showing nginx welcome page${NC}"
        return 1
    elif echo "$response" | grep -qi "502\|503\|504"; then
        echo -e "${YELLOW}⚠ Gateway error (service may be down)${NC}"
        return 1
    else
        echo -e "${GREEN}✓ Got response (not welcome page)${NC}"
        return 0
    fi
}

test_service "n8n.localhost"
test_service "comfyui.localhost"

echo ""
print_info "Diagnostic info:"
echo "  Check config: docker exec nginx-proxy cat /etc/nginx/conf.d/default.conf | less"
echo "  Check logs: docker compose logs nginx-proxy --tail 50"
echo "  Test URL: curl -v -H 'Host: n8n.localhost' http://localhost/"
