#!/bin/bash

set -e

SECRETS_DIR="./secrets"
BACKUP_DIR="./backups/secrets-backup-$(date +%Y%m%d_%H%M%S)"

echo "================================================"
echo "🔐 Generando archivos de secretos"
echo "================================================"

# Crear directorio de secretos
if [ -d "$SECRETS_DIR" ]; then
    echo "⚠️  Directorio de secretos existe. Creando backup..."
    mkdir -p "$BACKUP_DIR"
    cp -r "$SECRETS_DIR"/* "$BACKUP_DIR/" 2>/dev/null || true
    echo "✅ Backup guardado en: $BACKUP_DIR"
fi

mkdir -p "$SECRETS_DIR"
chmod 700 "$SECRETS_DIR"

# Función para generar secret
generate_secret() {
    local file=$1
    local length=${2:-32}
    
    if [ -f "$SECRETS_DIR/$file" ]; then
        echo "⏭️  $file ya existe, omitiendo..."
    else
        echo "🔑 Generando $file..."
        openssl rand -base64 $length | tr -d '\n' > "$SECRETS_DIR/$file"
        chmod 600 "$SECRETS_DIR/$file"
        echo "✅ $file creado"
    fi
}

# Función para generar secret simple
generate_simple_secret() {
    local file=$1
    local value=$2
    
    if [ -f "$SECRETS_DIR/$file" ]; then
        echo "⏭️  $file ya existe, omitiendo..."
    else
        echo "🔑 Generando $file..."
        echo -n "$value" > "$SECRETS_DIR/$file"
        chmod 600 "$SECRETS_DIR/$file"
        echo "✅ $file creado"
    fi
}

echo ""
echo "📝 Generando secretos de PostgreSQL..."
generate_simple_secret "postgres_user.txt" "${POSTGRES_USER:-n8n_user}"
generate_secret "postgres_password.txt" 32

echo ""
echo "📝 Generando secretos de n8n..."
generate_secret "n8n_encryption_key.txt" 32
generate_secret "n8n_jwt_secret.txt" 32
generate_secret "n8n_auth_jwt_secret.txt" 32
generate_secret "n8n_runners_auth_token.txt" 32

echo ""
echo "📝 Generando secretos de Redis..."
generate_secret "redis_password.txt" 32

echo ""
echo "📝 Generando secretos de Matrix..."
generate_secret "matrix_db_password.txt" 32

echo ""
echo "📝 Generando secretos de Authelia..."
generate_secret "authelia_jwt_secret.txt" 64
generate_secret "authelia_session_secret.txt" 64

echo ""
echo "📝 Generando secretos de Forgejo..."
generate_secret "forgejo_db_password.txt" 32
generate_secret "forgejo_mcp_token.txt" 32

echo ""
echo "📝 Generando secretos de Qdrant..."
generate_secret "qdrant_api_key.txt" 32

echo ""
echo "📝 Generando secretos de ComfyUI..."
generate_secret "comfyui_web_password.txt" 32

echo ""
echo "📝 Generando secretos de Browserless..."
generate_secret "browserless_token.txt" 32

echo ""
echo "📝 Generando secretos de Duplicati..."
generate_secret "duplicati_aws_access_key_id.txt" 32
generate_secret "duplicati_aws_secret_access_key.txt" 32
generate_secret "duplicati_passphrase.txt" 32

echo ""
echo "📝 Generando secretos de Grafana..."
generate_secret "grafana_admin_password.txt" 32

echo ""
echo "📝 Generando secretos de SMTP..."
generate_secret "smtp_password.txt" 32

echo ""
echo "================================================"
echo "✅ Todos los secretos generados exitosamente"
echo "================================================"

echo ""
echo "📋 Resumen de archivos creados:"
ls -lh "$SECRETS_DIR"

echo ""
echo "⚠️  IMPORTANTE: Añade 'secrets/' a .gitignore"
if ! grep -q "^secrets/$" .gitignore 2>/dev/null; then
    echo "secrets/" >> .gitignore
    echo "✅ 'secrets/' añadido a .gitignore"
else
    echo "✅ 'secrets/' ya está en .gitignore"
fi

echo ""
echo "🔐 Permisos del directorio de secretos:"
ls -ld "$SECRETS_DIR"

echo ""
echo "✅ Listo para iniciar los servicios"
