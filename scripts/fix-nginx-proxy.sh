#!/bin/bash
set -e

# Colors
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

print_header "Nginx Proxy & Authelia Configuration Fix"

# 1. Create Authelia location config for nginx-proxy
print_info "Creating Authelia location configuration..."
mkdir -p ./nginx-proxy/vhost.d

cat > ./nginx-proxy/vhost.d/default << 'EOF'
# Authelia protection for all services by default
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

# Error handling
error_page 401 = @error401;

location @error401 {
    return 302 https://auth.localhost/?rd=$scheme://$http_host$request_uri;
}
EOF

# 2. Create service-specific vhost configurations
print_info "Creating service-specific vhost configurations..."

# ComfyUI
cat > ./nginx-proxy/vhost.d/comfyui.localhost << 'EOF'
# Authelia authentication
auth_request /authelia;
auth_request_set $user $upstream_http_remote_user;
auth_request_set $groups $upstream_http_remote_groups;
auth_request_set $name $upstream_http_remote_name;
auth_request_set $email $upstream_http_remote_email;

# Pass auth info to backend
proxy_set_header Remote-User $user;
proxy_set_header Remote-Groups $groups;
proxy_set_header Remote-Name $name;
proxy_set_header Remote-Email $email;

# WebSocket support for ComfyUI
proxy_http_version 1.1;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";
proxy_set_header Host $host;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;

# Timeouts for long-running image generation
proxy_read_timeout 3600s;
proxy_send_timeout 3600s;
EOF

# n8n
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

# WebSocket support for n8n
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

# Uptime Kuma
cat > ./nginx-proxy/vhost.d/status.localhost << 'EOF'
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

# WebSocket support for Uptime Kuma
proxy_http_version 1.1;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";
proxy_set_header Host $host;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
EOF

# Grafana
cat > ./nginx-proxy/vhost.d/monitoring.localhost << 'EOF'
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

# Grafana specific headers
proxy_set_header Host $host;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
EOF

# Forgejo
cat > ./nginx-proxy/vhost.d/git.localhost << 'EOF'
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

# Forgejo specific
proxy_set_header Host $host;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;

# Large file uploads
client_max_body_size 100M;
EOF

print_success "Vhost configurations created"

# 3. Create Authelia configuration
print_info "Creating Authelia configuration..."
mkdir -p ./authelia

cat > ./authelia/configuration.yml << 'EOF'
---
theme: dark
default_2fa_method: ""

server:
  host: 0.0.0.0
  port: 9091
  path: ""
  asset_path: /config/assets/
  headers:
    csp_template: ""
  buffers:
    read: 4096
    write: 4096
  timeouts:
    read: 6s
    write: 6s
    idle: 30s
  endpoints:
    enable_pprof: false
    enable_expvars: false
    authz:
      forward-auth:
        implementation: ForwardAuth
        authn_strategies:
          - name: HeaderProxyAuthorization
            schemes:
              - Basic
          - name: CookieSession
        
log:
  level: info
  format: text
  file_path: ""
  keep_stdout: true

telemetry:
  metrics:
    enabled: false
    address: tcp://0.0.0.0:9959
    buffers:
      read: 4096
      write: 4096
    timeouts:
      read: 6s
      write: 6s
      idle: 30s

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
    - domain: auth.localhost
      policy: bypass
    
    # Public webhooks
    - domain: n8n.localhost
      resources:
        - "^/webhook.*$"
        - "^/webhook-test.*$"
      policy: bypass
    
    # Protected services - require authentication
    - domain:
        - n8n.localhost
        - comfyui.localhost
        - status.localhost
        - monitoring.localhost
        - git.localhost
        - ollama.localhost
        - libretranslate.localhost
        - languagetool.localhost
      policy: one_factor

session:
  name: authelia_session
  domain: localhost
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
    database_index: 0

regulation:
  max_retries: 3
  find_time: 2m
  ban_time: 5m

storage:
  local:
    path: /config/db.sqlite3

notifier:
  disable_startup_check: false
  smtp:
    host: smtp.tinet.cat
    port: 465
    timeout: 5s
    username: your-email@example.com
    sender: "Authelia <noreply@example.com>"
    identifier: auth.localhost
    subject: "[Authelia] {title}"
    startup_check_address: test@authelia.com
    disable_require_tls: false
    disable_html_emails: false
    tls:
      server_name: smtp.tinet.cat
      skip_verify: false
      minimum_version: TLS1.2
      maximum_version: TLS1.3
EOF

cat > ./authelia/users_database.yml << 'EOF'
---
users:
  admin:
    disabled: false
    displayname: "Admin User"
    password: "$argon2id$v=19$m=65536,t=3,p=4$your-hashed-password-here"
    email: admin@example.com
    groups:
      - admins
      - dev
EOF

print_success "Authelia configuration created"

# 4. Fix nginx-proxy volume mounts
print_info "Checking nginx-proxy volume configuration..."

if ! grep -q "./nginx-proxy/vhost.d:/etc/nginx/vhost.d" docker-compose.yml; then
    print_warning "nginx-proxy vhost.d volume mount is incorrect"
    print_info "Please update nginx-proxy volumes in docker-compose.yml:"
    echo ""
    echo "    volumes:"
    echo "      - /var/run/docker.sock:/tmp/docker.sock:ro"
    echo "      - certs:/etc/nginx/certs:ro"
    echo "      - confd:/etc/nginx/conf.d"
    echo "      - ./nginx-proxy/vhost.d:/etc/nginx/vhost.d:ro  # ← THIS LINE"
    echo "      - html:/usr/share/nginx/html"
fi

print_header "Next Steps"

cat << 'EOF'
1. Generate Authelia admin password:
   docker run --rm authelia/authelia:latest authelia crypto hash generate argon2 --password 'your-secure-password'
   
   Copy the hash and update ./authelia/users_database.yml

2. Update SMTP settings in ./authelia/configuration.yml:
   - smtp.username
   - smtp.sender

3. Restart services:
   docker compose down
   docker compose --profile gpu-nvidia up -d

4. Test access:
   - http://auth.localhost - Authelia portal
   - http://n8n.localhost - Should redirect to Authelia
   - http://comfyui.localhost - Should redirect to Authelia

5. Check logs if issues:
   docker compose logs nginx-proxy
   docker compose logs authelia
   docker compose logs n8n

6. Verify nginx-proxy can see services:
   docker exec nginx-proxy cat /etc/nginx/conf.d/default.conf

Common issues:
- If services show nginx welcome page: Check VIRTUAL_HOST env vars
- If auth doesn't work: Check Authelia logs and Redis connection
- If webhooks fail: Verify bypass rules in access_control
EOF

print_success "Configuration files created successfully!"
print_warning "Remember to update the Authelia admin password hash!"
