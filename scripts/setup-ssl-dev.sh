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

print_header "Setup Self-Signed SSL Certificates for Development"

# Create certs directory
mkdir -p ./certs
cd ./certs

DOMAINS=(
    "auth.local.dev"
    "n8n.local.dev"
    "comfyui.local.dev"
    "status.local.dev"
    "monitoring.local.dev"
    "git.local.dev"
    "ollama.local.dev"
    "libretranslate.local.dev"
    "languagetool.local.dev"
)

print_info "Generating self-signed certificates for development..."

for domain in "${DOMAINS[@]}"; do
    echo -n "  $domain... "
    
    # Generate private key
    openssl genrsa -out "${domain}.key" 2048 2>/dev/null
    
    # Generate certificate
    openssl req -new -x509 -key "${domain}.key" -out "${domain}.crt" -days 365 -subj "/CN=${domain}" 2>/dev/null
    
    echo "✓"
done

print_success "Certificates generated"

cd ..

# Create nginx-proxy vhost configs with SSL
print_info "Creating vhost.d configurations..."
mkdir -p ./nginx-proxy/vhost.d

# Default config with Authelia
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

# n8n config
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
    proxy_set_header Host $host;
}

location /webhook-test {
    auth_request off;
    proxy_pass http://n8n:5678;
    proxy_set_header Host $host;
}
EOF

print_success "Vhost configs created"

# Update Authelia configuration
print_info "Updating Authelia configuration for HTTPS..."
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
  filesystem:
    filename: /config/notification.txt

identity_validation:
  reset_password:
    jwt_lifespan: 5m
EOF

print_success "Authelia configuration updated"

# Generate admin password
print_info "Generating admin password..."
echo ""
echo "Enter admin password (default: admin123):"
read -s ADMIN_PASSWORD
ADMIN_PASSWORD=${ADMIN_PASSWORD:-admin123}

HASH=$(docker run --rm authelia/authelia:latest authelia crypto hash generate argon2 --password "$ADMIN_PASSWORD" 2>/dev/null | grep "Digest:" | awk '{print $2}')

cat > ./authelia/users_database.yml << EOF
---
users:
  admin:
    disabled: false
    displayname: "Admin User"
    password: "$HASH"
    email: admin@local.dev
    groups:
      - admins
      - dev
EOF

print_success "Admin user created"

print_header "Setup Complete!"

cat << 'EOF'

✅ Self-signed SSL certificates generated
✅ Authelia configured for HTTPS
✅ Nginx vhost configs created
✅ Admin user created

⚠️  IMPORTANT: Trust the self-signed certificates
   In your browser, visit each domain and accept the certificate warning:
   - https://auth.local.dev
   - https://n8n.local.dev
   - https://comfyui.local.dev

🔐 Login credentials:
   Username: admin
   Password: (the one you entered)

🚀 Next steps:
   1. Restart services:
      docker compose down
      docker compose --profile gpu-nvidia up -d
   
   2. Wait 30 seconds for startup
   
   3. Test Authelia:
      curl -k https://auth.local.dev:9091/api/health
   
   4. Browse to: https://n8n.local.dev
      (Accept certificate warning, then login with Authelia)

📝 Note: The -k flag ignores certificate warnings for curl.
      In production, use real SSL certificates from Let's Encrypt.
EOF
