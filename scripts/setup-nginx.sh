#!/bin/bash

set -e

echo "================================================"
echo "🔧 Configurando nginx-proxy"
echo "================================================"

# Crear directorios
mkdir -p nginx-proxy/conf.d
mkdir -p logs/nginx

echo "📁 Directorios creados"

# uploadsize.conf
cat > nginx-proxy/uploadsize.conf << 'EOF'
# Increase upload size limits for file uploads
client_max_body_size 100M;
client_body_buffer_size 128k;
client_body_timeout 300s;
EOF

echo "✅ uploadsize.conf creado"

# proxy.conf
cat > nginx-proxy/proxy.conf << 'EOF'
# HTTP 1.1 support
proxy_http_version 1.1;
proxy_buffering off;
proxy_set_header Host $http_host;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection $proxy_connection;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $proxy_x_forwarded_proto;
proxy_set_header X-Forwarded-Ssl $proxy_x_forwarded_ssl;
proxy_set_header X-Forwarded-Port $proxy_x_forwarded_port;
proxy_set_header X-Forwarded-Host $http_host;

# Mitigate httpoxy attack
proxy_set_header Proxy "";

# Timeout settings
proxy_connect_timeout 600;
proxy_send_timeout 600;
proxy_read_timeout 600;
send_timeout 600;
EOF

echo "✅ proxy.conf creado"

# authelia.conf - Configuración básica sin Authelia activa
cat > nginx-proxy/conf.d/authelia.conf << 'EOF'
# Rate limiting zones
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=auth_limit:10m rate=5r/m;
limit_req_zone $binary_remote_addr zone=login_limit:10m rate=3r/m;

# Security headers
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "no-referrer-when-downgrade" always;

# Gzip compression
gzip on;
gzip_vary on;
gzip_proxied any;
gzip_comp_level 6;
gzip_types text/plain text/css text/xml text/javascript application/json application/javascript application/xml+rss application/rss+xml font/truetype font/opentype application/vnd.ms-fontobject image/svg+xml;
EOF

echo "✅ authelia.conf creado"

# Permisos
chmod 644 nginx-proxy/*.conf
chmod 644 nginx-proxy/conf.d/*.conf

echo ""
echo "================================================"
echo "✅ nginx-proxy configurado correctamente"
echo "================================================"
echo ""
echo "📋 Archivos creados:"
ls -lh nginx-proxy/
ls -lh nginx-proxy/conf.d/

echo ""
echo "🚀 Ahora puedes ejecutar: bash start.sh --voice"
