#!/bin/bash
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo -e "\n${BLUE}================================================${NC}"
    echo -e "${BLUE}🔐 $1${NC}"
    echo -e "${BLUE}================================================${NC}\n"
}

print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }
print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }

print_header "Complete Authelia Setup with Self-Signed Certificates"

# 1. Stop Authelia
print_info "Stopping Authelia..."
docker compose stop authelia

# 2. Generate Self-Signed Certificates
print_info "Generating self-signed SSL certificates..."
mkdir -p ./certs

# Generate wildcard certificate for *.localhost
openssl req -x509 -nodes -newkey rsa:2048 \
  -keyout ./certs/localhost.key \
  -out ./certs/localhost.crt \
  -sha256 -days 365 \
  -subj '/CN=*.localhost' \
  -addext 'subjectAltName=DNS:*.localhost,DNS:localhost'

# Copy as default
cp ./certs/localhost.crt ./certs/default.crt
cp ./certs/localhost.key ./certs/default.key

# Copy for each specific domain
for domain in auth n8n comfyui status git matrix duplicati ollama libretranslate languagetool; do
    cp ./certs/localhost.crt ./certs/${domain}.localhost.crt
    cp ./certs/localhost.key ./certs/${domain}.localhost.key
done

print_success "SSL certificates generated"

# 3. Create Authelia Configuration
print_info "Creating Authelia configuration..."

cat > ./authelia/configuration.yml << 'EOF'
---
theme: dark

server:
  address: 'tcp://0.0.0.0:9091/'

log:
  level: info
  keep_stdout: true

telemetry:
  metrics:
    enabled: false

totp:
  disable: false
  issuer: localhost
  algorithm: sha1
  digits: 6
  period: 30
  skew: 1
  secret_size: 32

webauthn:
  disable: true

ntp:
  address: 'time.cloudflare.com:123'
  version: 4
  max_desync: 3s
  disable_startup_check: false
  disable_failure: false

authentication_backend:
  password_reset:
    disable: false
  refresh_interval: 5m
  
  file:
    path: /config/users_database.yml
    password:
      algorithm: argon2
      argon2:
        variant: argon2id
        iterations: 3
        memory: 65536
        parallelism: 4
        key_length: 32
        salt_length: 16

access_control:
  default_policy: one_factor
  
  rules:
    # Authelia portal - always accessible
    - domain: auth.localhost
      policy: bypass
    
    # Public webhooks - no auth required
    - domain: n8n.localhost
      resources:
        - '^/webhook.*$'
        - '^/webhook-test.*$'
      policy: bypass
    
    # All other services require authentication
    - domain:
        - n8n.localhost
        - comfyui.localhost
        - status.localhost
        - monitoring.localhost
        - git.localhost
        - matrix.localhost
        - duplicati.localhost
        - ollama.localhost
        - libretranslate.localhost
        - languagetool.localhost
      policy: one_factor

session:
  same_site: lax
  expiration: 1h
  inactivity: 5m
  remember_me: 1M
  
  cookies:
    - domain: localhost
      authelia_url: https://auth.localhost
      default_redirection_url: https://n8n.localhost
      
  redis:
    host: redis
    port: 6379

regulation:
  max_retries: 3
  find_time: 2m
  ban_time: 5m

storage:
  local:
    path: /config/db.sqlite3

notifier:
  filesystem:
    filename: /config/notification.txt

identity_validation:
  reset_password:
    jwt_lifespan: 5m
EOF

print_success "Authelia configuration created"

# 4. Generate Admin Password
print_info "Generating admin password..."
echo ""
echo -n "Enter admin password (press Enter for 'admin123'): "
read -s ADMIN_PASSWORD
echo ""
ADMIN_PASSWORD=${ADMIN_PASSWORD:-admin123}

HASH=$(docker run --rm authelia/authelia:latest \
  authelia crypto hash generate argon2 --password "$ADMIN_PASSWORD" 2>/dev/null | \
  grep "Digest:" | awk '{print $2}')

if [ -z "$HASH" ]; then
    print_error "Failed to generate password hash"
    exit 1
fi

cat > ./authelia/users_database.yml << EOF
---
users:
  admin:
    disabled: false
    displayname: "Admin User"
    password: "$HASH"
    email: admin@localhost
    groups:
      - admins
      - dev
EOF

print_success "Admin user created (username: admin, password: ${ADMIN_PASSWORD})"

# 5. Fix docker-compose.yml nginx-proxy section
print_info "Checking docker-compose.yml nginx-proxy configuration..."

# Check if HTTPS_METHOD is set correctly
if grep -q "HTTPS_METHOD=noredirect" docker-compose.yml; then
    print_warning "HTTPS_METHOD is set to 'noredirect', changing to 'redirect'..."
    sed -i 's/HTTPS_METHOD=noredirect/HTTPS_METHOD=redirect/' docker-compose.yml
fi

# Verify volumes are correct
if ! grep -q "./nginx-proxy/vhost.d:/etc/nginx/vhost.d:ro" docker-compose.yml; then
    print_error "vhost.d volume mount is missing in docker-compose.yml!"
    echo "Please add this to nginx-proxy volumes:"
    echo "  - ./nginx-proxy/vhost.d:/etc/nginx/vhost.d:ro"
fi

print_success "docker-compose.yml checked"

# 6. Update nginx-proxy vhost.d files
print_info "Updating nginx-proxy vhost configurations..."

# Create default vhost config
cat > ./nginx-proxy/vhost.d/default << 'EOF'
# Authelia protection
location /authelia {
    internal;
    set $upstream_authelia http://authelia:9091/api/authz/forward-auth;
    proxy_pass $upstream_authelia;
    
    proxy_set_header X-Original-URL $scheme://$http_host$request_uri;
    proxy_set_header X-Forwarded-Method $request_method;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Host $http_host;
    proxy_set_header X-Forwarded-Uri $request_uri;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_set_header Content-Length "";
    proxy_set_header Connection "";
    
    proxy_pass_request_body off;
    proxy_http_version 1.1;
}

error_page 401 = @error401;

location @error401 {
    return 302 https://auth.localhost/?rd=$scheme://$http_host$request_uri;
}
EOF

# n8n with Authelia
cat > ./nginx-proxy/vhost.d/n8n.localhost << 'EOF'
# Authelia authentication
auth_request /authelia;
auth_request_set $user $upstream_http_remote_user;
auth_request_set $groups $upstream_http_remote_groups;
auth_request_set $name $upstream_http_remote_name;
auth_request_set $email $upstream_http_remote_email;

proxy_set_header Remote-User $user;
proxy_set_header Remote-Groups $groups;
proxy_set_header Remote-Name $name;
proxy_set_header Remote-Email $email;

# WebSocket support
proxy_http_version 1.1;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";
proxy_set_header Host $host;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;

# Allow webhooks without auth
location /webhook {
    auth_request off;
    proxy_pass http://n8n:5678;
}

location /webhook-test {
    auth_request off;
    proxy_pass http://n8n:5678;
}
EOF

# ComfyUI with Authelia
cat > ./nginx-proxy/vhost.d/comfyui.localhost << 'EOF'
# Authelia authentication
auth_request /authelia;
auth_request_set $user $upstream_http_remote_user;

proxy_set_header Remote-User $user;

# WebSocket + long timeouts
proxy_http_version 1.1;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";
proxy_read_timeout 3600s;
proxy_send_timeout 3600s;
EOF

# Status (Uptime Kuma) with Authelia
cat > ./nginx-proxy/vhost.d/status.localhost << 'EOF'
# Authelia authentication
auth_request /authelia;
auth_request_set $user $upstream_http_remote_user;

proxy_set_header Remote-User $user;

# WebSocket support
proxy_http_version 1.1;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";
EOF

# Empty files for others (will use default)
touch ./nginx-proxy/vhost.d/git.localhost
touch ./nginx-proxy/vhost.d/matrix.localhost
touch ./nginx-proxy/vhost.d/duplicati.localhost

print_success "Vhost configurations updated"

# 7. Restart services
print_info "Restarting services..."
docker compose down
sleep 2
docker compose --profile gpu-nvidia up -d

print_info "Waiting for services to start..."
sleep 20

# 8. Check Authelia status
print_info "Checking Authelia status..."
if docker ps | grep -q authelia; then
    print_success "Authelia container is running"
    
    # Check logs
    if docker compose logs authelia --tail 10 | grep -q "listening for non-TLS connections"; then
        print_success "Authelia started successfully!"
    else
        print_warning "Authelia may have errors, checking logs..."
        docker compose logs authelia --tail 20
    fi
else
    print_error "Authelia is not running!"
    docker compose logs authelia --tail 30
fi

# 9. Final instructions
print_header "Setup Complete!"

cat << 'INSTRUCTIONS'

✅ Self-signed SSL certificates generated
✅ Authelia configured for development
✅ Nginx-proxy configured with Authelia integration
✅ Services restarted

🔐 Login Credentials:
   Username: admin
   Password: (the one you entered, or 'admin123')

🌐 Access URLs (HTTPS):
   https://auth.localhost     - Authelia portal
   https://n8n.localhost      - n8n (protected)
   https://comfyui.localhost  - ComfyUI (protected)
   https://status.localhost   - Uptime Kuma (protected)

⚠️  IMPORTANT - Browser Setup:

1. Accept self-signed certificates:
   When you first visit https://auth.localhost, your browser will show
   a security warning. Click "Advanced" → "Proceed to auth.localhost"
   
   You'll need to do this for each domain (n8n, comfyui, status, etc.)

2. Alternative - Trust the certificate (recommended):
   
   Chrome/Edge:
   - Visit https://auth.localhost
   - Click the "Not Secure" warning → Certificate → Details
   - Export certificate → Save as localhost.crt
   - Settings → Privacy & Security → Security → Manage certificates
   - Import → Select localhost.crt → Place in "Trusted Root Certification Authorities"
   
   Firefox:
   - Visit https://auth.localhost  
   - Click "Advanced" → "Accept the Risk and Continue"
   - Repeat for each domain

3. Test the setup:
   - Visit https://auth.localhost (should load Authelia portal)
   - Login with admin / (your password)
   - Visit https://n8n.localhost (should redirect to Authelia, then to n8n)

📝 Troubleshooting:

If Authelia won't start:
   docker compose logs authelia --tail 50

If you get 502 errors:
   docker compose ps | grep -E "authelia|nginx-proxy"
   docker exec nginx-proxy nginx -t

If authentication doesn't work:
   Check nginx-proxy logs: docker compose logs nginx-proxy --tail 30

🔄 To disable Authelia (go back to no auth):
   docker compose stop authelia
   Remove auth_request lines from vhost.d/*.localhost files

INSTRUCTIONS

print_success "Authelia setup complete! 🎉"
