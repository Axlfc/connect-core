#!/bin/bash
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo -e "\n${BLUE}================================================${NC}"
    echo -e "${BLUE}🔧 $1${NC}"
    echo -e "${BLUE}================================================${NC}\n"
}

print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }
print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }

print_header "Authelia Complete Fix"

# 1. Stop Authelia
print_info "Stopping Authelia..."
docker compose stop authelia || true

# 2. Create config directory
print_info "Creating Authelia config directory..."
mkdir -p ./authelia

# 3. Create fixed configuration
print_info "Creating fixed configuration.yml..."
cat > ./authelia/configuration.yml << 'EOF'
---
theme: dark
default_2fa_method: ""

server:
  address: 'tcp://0.0.0.0:9091/'

log:
  level: info
  format: text
  keep_stdout: true

telemetry:
  metrics:
    enabled: false

totp:
  disable: false
  issuer: authelia.com
  algorithm: sha1
  digits: 6
  period: 30
  skew: 1
  secret_size: 32

webauthn:
  disable: true

ntp:
  address: "time.cloudflare.com:123"
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
  default_policy: deny
  
  rules:
    # Authelia portal
    - domain: auth.local.dev
      policy: bypass
    
    # Public webhooks
    - domain: n8n.local.dev
      resources:
        - "^/webhook.*$"
        - "^/webhook-test.*$"
      policy: bypass
    
    # Protected services
    - domain:
        - n8n.local.dev
        - comfyui.local.dev
        - status.local.dev
        - monitoring.local.dev
        - git.local.dev
        - ollama.local.dev
        - libretranslate.local.dev
        - languagetool.local.dev
      policy: one_factor

session:
  name: authelia_session
  same_site: lax
  expiration: 1h
  inactivity: 5m
  remember_me: 1M
  
  cookies:
    - domain: local.dev
      authelia_url: https://auth.local.dev
      default_redirection_url: https://n8n.local.dev

  redis:
    host: redis
    port: 6379
    database_index: 0

regulation:
  max_retries: 3
  find_time: 2m
  ban_time: 5m

storage:
  local:
    path: /config/db.sqlite3

notifier:
  disable_startup_check: true
  smtp:
    address: 'smtp://smtp.tinet.cat:465'
    timeout: 5s
    username: your-email@example.com
    sender: "Authelia <noreply@example.com>"
    identifier: auth.local.dev
    subject: "[Authelia] {title}"
    startup_check_address: test@authelia.com
    disable_require_tls: false
    disable_html_emails: false
    tls:
      server_name: smtp.tinet.cat
      skip_verify: false
      minimum_version: TLS1.2
      maximum_version: TLS1.3

identity_validation:
  reset_password:
    jwt_lifespan: 5m
EOF

print_success "Configuration created"

# 4. Generate password hash
print_info "Generating password hash..."
echo ""
echo "Enter admin password (press Enter for default 'admin123'):"
read -s ADMIN_PASSWORD
ADMIN_PASSWORD=${ADMIN_PASSWORD:-admin123}

HASH=$(docker run --rm authelia/authelia:latest authelia crypto hash generate argon2 --password "$ADMIN_PASSWORD" 2>/dev/null | grep "Digest:" | awk '{print $2}')

if [ -z "$HASH" ]; then
    print_error "Failed to generate password hash"
    exit 1
fi

print_success "Password hash generated"

# 5. Create users database
print_info "Creating users_database.yml..."
cat > ./authelia/users_database.yml << EOF
---
users:
  admin:
    disabled: false
    displayname: "Admin User"
    password: "$HASH"
    email: admin@example.com
    groups:
      - admins
      - dev
EOF

print_success "Users database created"

# 6. Update /etc/hosts
print_info "Updating /etc/hosts..."
HOSTS_ENTRIES=(
  "127.0.0.1 auth.local.dev"
  "127.0.0.1 n8n.local.dev"
  "127.0.0.1 comfyui.local.dev"
  "127.0.0.1 status.local.dev"
  "127.0.0.1 monitoring.local.dev"
  "127.0.0.1 git.local.dev"
  "127.0.0.1 ollama.local.dev"
  "127.0.0.1 libretranslate.local.dev"
  "127.0.0.1 languagetool.local.dev"
)

echo ""
echo "Add these lines to /etc/hosts:"
echo "─────────────────────────────────────"
for entry in "${HOSTS_ENTRIES[@]}"; do
    echo "$entry"
done
echo "─────────────────────────────────────"
echo ""
echo "Run this command to add them:"
echo ""
echo "sudo bash -c 'cat >> /etc/hosts << \"EOFHOSTS\""
for entry in "${HOSTS_ENTRIES[@]}"; do
    echo "$entry"
done
echo "EOFHOSTS'"
echo ""

read -p "Press Enter when you've updated /etc/hosts..."

# 7. Update docker-compose.yml environment variables
print_info "You need to update docker-compose.yml manually:"
echo ""
echo "Change all VIRTUAL_HOST variables from:"
echo "  - VIRTUAL_HOST=service.localhost"
echo ""
echo "To:"
echo "  - VIRTUAL_HOST=service.local.dev"
echo ""
echo "Services to update:"
echo "  - authelia: VIRTUAL_HOST=auth.local.dev"
echo "  - n8n: VIRTUAL_HOST=n8n.local.dev"
echo "  - comfyui: VIRTUAL_HOST=comfyui.local.dev"
echo "  - uptime-kuma: VIRTUAL_HOST=status.local.dev"
echo "  - grafana: VIRTUAL_HOST=monitoring.local.dev"
echo "  - forgejo: VIRTUAL_HOST=git.local.dev"
echo "  - ollama-proxy: VIRTUAL_HOST=ollama.local.dev"
echo "  - libretranslate: VIRTUAL_HOST=libretranslate.local.dev"
echo "  - languagetool: VIRTUAL_HOST=languagetool.local.dev"
echo ""

read -p "Press Enter when you've updated docker-compose.yml..."

# 8. Update vhost.d configurations
print_info "Updating vhost.d configurations..."
mkdir -p ./nginx-proxy/vhost.d

# Update default
cat > ./nginx-proxy/vhost.d/default << 'EOF'
# Authelia protection
location /authelia {
    internal;
    set $upstream_authelia http://authelia:9091/api/verify;
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
    proxy_next_upstream error timeout invalid_header http_500 http_502 http_503;
    proxy_http_version 1.1;
    proxy_ssl_server_name on;
    proxy_pass_request_headers on;
}

error_page 401 = @error401;

location @error401 {
    return 302 https://auth.local.dev/?rd=$scheme://$http_host$request_uri;
}
EOF

# Update n8n.local.dev
cat > ./nginx-proxy/vhost.d/n8n.local.dev << 'EOF'
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

# Similar configs for other services
for service in comfyui status monitoring git; do
    domain="${service}.local.dev"
    if [ "$service" = "status" ]; then
        domain="status.local.dev"
        port="3001"
        upstream="uptime-kuma"
    elif [ "$service" = "monitoring" ]; then
        port="3000"
        upstream="grafana"
    elif [ "$service" = "git" ]; then
        port="3000"
        upstream="forgejo"
    elif [ "$service" = "comfyui" ]; then
        port="8188"
        upstream="comfyui"
    fi
    
    cat > "./nginx-proxy/vhost.d/${domain}" << EOF
# Authelia authentication
auth_request /authelia;
auth_request_set \$user \$upstream_http_remote_user;
auth_request_set \$groups \$upstream_http_remote_groups;
auth_request_set \$name \$upstream_http_remote_name;
auth_request_set \$email \$upstream_http_remote_email;

proxy_set_header Remote-User \$user;
proxy_set_header Remote-Groups \$groups;
proxy_set_header Remote-Name \$name;
proxy_set_header Remote-Email \$email;

# WebSocket support
proxy_http_version 1.1;
proxy_set_header Upgrade \$http_upgrade;
proxy_set_header Connection "upgrade";
proxy_set_header Host \$host;
proxy_set_header X-Real-IP \$remote_addr;
proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto \$scheme;
EOF
done

print_success "Vhost configurations updated"

# 9. Restart services
print_info "Restarting services..."
docker compose down
sleep 2
docker compose --profile gpu-nvidia up -d

print_header "Setup Complete!"

cat << 'EOF'

✅ Authelia configuration fixed
✅ Password hash generated
✅ Users database created
✅ Vhost configurations updated

🔐 Login credentials:
   Username: admin
   Password: (the one you entered, default: admin123)

🌐 Access URLs:
   - https://auth.local.dev - Authelia portal
   - https://n8n.local.dev - n8n (protected)
   - https://comfyui.local.dev - ComfyUI (protected)
   - https://status.local.dev - Uptime Kuma (protected)

📝 Next steps:
   1. Wait 30 seconds for services to start
   2. Test: curl -v http://auth.local.dev:9091/api/health
   3. Check logs: docker compose logs authelia
   4. Browse to: http://n8n.local.dev (should redirect to Authelia)

⚠️  IMPORTANT:
   - Make sure /etc/hosts is updated with local.dev domains
   - Make sure docker-compose.yml has VIRTUAL_HOST updated
   - SMTP is disabled (disable_startup_check: true)

EOF

print_info "Checking Authelia logs in 10 seconds..."
sleep 10
docker compose logs authelia --tail 20
