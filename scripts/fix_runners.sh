#!/bin/bash

# fix-runners.sh - Script para corregir automáticamente los n8n runners
# Uso: ./fix-runners.sh

set -e

# Colores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=================================================="
echo "🔧 Script de Corrección de n8n Task Runners"
echo -e "==================================================${NC}"
echo ""

# Función para preguntar confirmación
confirm() {
    read -p "$1 (y/n): " -n 1 -r
    echo
    [[ $REPLY =~ ^[Yy]$ ]]
}

# 1. Backup de archivos actuales
echo -e "${YELLOW}📦 Paso 1: Creando backups...${NC}"
BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

if [ -f "Dockerfile.runners" ]; then
    cp Dockerfile.runners "$BACKUP_DIR/"
    echo -e "${GREEN}✅ Backup de Dockerfile.runners creado${NC}"
fi

if [ -f "docker-compose.yml" ]; then
    cp docker-compose.yml "$BACKUP_DIR/"
    echo -e "${GREEN}✅ Backup de docker-compose.yml creado${NC}"
fi

if [ -f "n8n-task-runners.json" ]; then
    cp n8n-task-runners.json "$BACKUP_DIR/"
    echo -e "${GREEN}✅ Backup de n8n-task-runners.json creado${NC}"
fi

echo ""

# 2. Verificar archivo .env
echo -e "${YELLOW}🔍 Paso 2: Verificando .env...${NC}"
if [ ! -f .env ]; then
    echo -e "${RED}❌ Archivo .env no encontrado${NC}"
    echo "Creando archivo .env de ejemplo..."
    cat > .env << 'EOF'
# Database
POSTGRES_DB=n8n_db
POSTGRES_USER=n8n_user
POSTGRES_PASSWORD=changeme-secure-password

# n8n
N8N_ENCRYPTION_KEY=changeme-encryption-key-min-32-chars
N8N_USER_MANAGEMENT_JWT_SECRET=changeme-jwt-secret
N8N_AUTH_JWT_SECRET=changeme-auth-jwt-secret

# Runners - GENERA UN TOKEN SEGURO
N8N_RUNNERS_AUTH_TOKEN=changeme-runners-token-use-openssl-rand

# Webhook
WEBHOOK_URL=http://n8n.cognito.local

# User
PUID=1000
PGID=1000
EOF
    echo -e "${YELLOW}⚠️  Archivo .env creado. DEBES editar los valores antes de continuar${NC}"
    echo "   Genera el token con: openssl rand -base64 32"
    exit 1
fi

if grep -q "changeme" .env; then
    echo -e "${YELLOW}⚠️  Advertencia: Tu archivo .env contiene valores 'changeme'${NC}"
    echo "   Recomendamos generar valores seguros antes de continuar"
    if ! confirm "¿Continuar de todos modos?"; then
        echo "Abortado."
        exit 1
    fi
fi

if ! grep -q "N8N_RUNNERS_AUTH_TOKEN=" .env; then
    echo -e "${YELLOW}⚠️  Variable N8N_RUNNERS_AUTH_TOKEN no encontrada en .env${NC}"
    echo "Generando token..."
    TOKEN=$(openssl rand -base64 32)
    echo "" >> .env
    echo "# Runners Auth Token (generado: $(date))" >> .env
    echo "N8N_RUNNERS_AUTH_TOKEN=$TOKEN" >> .env
    echo -e "${GREEN}✅ Token generado y añadido a .env${NC}"
fi

echo -e "${GREEN}✅ Archivo .env verificado${NC}"
echo ""

# 3. Actualizar Dockerfile.runners
echo -e "${YELLOW}📝 Paso 3: Actualizando Dockerfile.runners...${NC}"

cat > Dockerfile.runners << 'EOF'
FROM n8nio/runners:1.121.0

USER root

# Install build dependencies for Python packages
RUN apk add --no-cache \
    gcc g++ musl-dev python3-dev openblas-dev postgresql-dev \
    bash git curl make cmake pkgconfig linux-headers build-base \
    libxml2-dev libxslt-dev rust cargo gfortran lapack-dev

# Create virtual environment
RUN python3 -m venv /home/runner/custom-venv
ENV PATH="/home/runner/custom-venv/bin:$PATH"

# Enable PyO3 forward compatibility for Python 3.13
ENV PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1

# Upgrade pip
RUN /home/runner/custom-venv/bin/pip install --upgrade pip

# ✅ CRITICAL FIX: Install compatible websockets version
# The n8n runners require websockets with asyncio support but NOT 13.x
# Version 12.0 is the last stable version before the API breaking changes
RUN /home/runner/custom-venv/bin/pip install --no-cache-dir \
    'websockets>=11.0,<13.0' \
    numpy==1.26.4 \
    pandas==2.2.3 \
    requests==2.32.3 \
    beautifulsoup4==4.12.3 \
    lxml==5.2.2 \
    pillow==11.0.0 \
    openpyxl==3.1.3 \
    scikit-learn==1.5.0 \
    matplotlib==3.9.0 \
    scipy==1.13.1 \
    seaborn==0.13.2 \
    openai==1.35.3 \
    langchain==0.2.5 \
    tiktoken==0.8.0 \
    fastapi==0.111.0 \
    uvicorn==0.30.1 \
    huggingface-hub==0.23.4

# Development packages
RUN /home/runner/custom-venv/bin/pip install --no-cache-dir \
    black==24.4.2 \
    isort==5.13.2 \
    flake8==7.1.0 \
    mypy==1.10.0 \
    pytest==8.2.2 \
    ipython==8.25.0 \
    sqlalchemy==2.0.31 \
    redis==5.0.7 \
    psycopg2-binary==2.9.10

# Fix ownership
RUN chown -R runner:runner /home/runner/custom-venv

# Install Node.js packages
RUN cd /opt/runners/task-runner-javascript && pnpm add moment@2.30.1 uuid@10.0.0

# Install Python packages for task runner
RUN cd /opt/runners/task-runner-python && uv pip install numpy==1.26.4 pandas==2.2.3

# Copy task runner configuration
COPY n8n-task-runners.json /etc/n8n-task-runners.json

USER runner

# Verify websockets is available and compatible
RUN /home/runner/custom-venv/bin/python -c "import websockets; print(f'✅ websockets {websockets.__version__} available')"
EOF

echo -e "${GREEN}✅ Dockerfile.runners actualizado${NC}"
echo ""

# 4. Actualizar n8n-task-runners.json
echo -e "${YELLOW}📝 Paso 4: Actualizando n8n-task-runners.json...${NC}"

cat > n8n-task-runners.json << 'EOF'
{
  "task-runners": [
    {
      "runner-type": "javascript",
      "workdir": "/home/runner",
      "command": "/usr/local/bin/node",
      "args": [
        "--disable-proto=delete",
        "/opt/runners/task-runner-javascript/dist/start.js"
      ],
      "health-check-server-port": "5681",
      "allowed-env": [
        "PATH",
        "HOME",
        "GENERIC_TIMEZONE",
        "NODE_OPTIONS",
        "N8N_RUNNERS_AUTO_SHUTDOWN_TIMEOUT",
        "N8N_RUNNERS_TASK_TIMEOUT",
        "N8N_RUNNERS_MAX_CONCURRENCY",
        "N8N_RUNNERS_TASK_BROKER_URI",
        "N8N_RUNNERS_HEALTH_CHECK_SERVER_ENABLED",
        "N8N_RUNNERS_HEALTH_CHECK_SERVER_PORT",
        "N8N_RUNNERS_HEALTH_CHECK_SERVER_HOST",
        "NODE_FUNCTION_ALLOW_BUILTIN",
        "NODE_FUNCTION_ALLOW_EXTERNAL",
        "NODE_FUNCTION_DENY_BUILTIN",
        "N8N_RUNNERS_ALLOW_PROTOTYPE_MUTATION",
        "N8N_SENTRY_DSN",
        "N8N_VERSION",
        "ENVIRONMENT",
        "DEPLOYMENT_NAME"
      ],
      "env-overrides": {
        "NODE_FUNCTION_ALLOW_EXTERNAL": "axios,cheerio,form-data,moment,uuid",
        "N8N_RUNNERS_HEALTH_CHECK_SERVER_HOST": "0.0.0.0",
        "NODE_FUNCTION_DENY_BUILTIN": "child_process,cluster,dgram,dns,fs,http,https,net,os,repl,sys,tls,tty,v8,vm,worker_threads,zlib"
      }
    },
    {
      "runner-type": "python",
      "workdir": "/home/runner",
      "command": "/home/runner/custom-venv/bin/python",
      "args": ["-m", "src.main"],
      "health-check-server-port": "5682",
      "allowed-env": [
        "PATH",
        "HOME",
        "PYTHONPATH",
        "PYTHONUNBUFFERED",
        "N8N_RUNNERS_LAUNCHER_LOG_LEVEL",
        "N8N_RUNNERS_AUTO_SHUTDOWN_TIMEOUT",
        "N8N_RUNNERS_TASK_TIMEOUT",
        "N8N_RUNNERS_MAX_CONCURRENCY",
        "N8N_RUNNERS_TASK_BROKER_URI",
        "N8N_RUNNERS_HEALTH_CHECK_SERVER_ENABLED",
        "N8N_RUNNERS_HEALTH_CHECK_SERVER_PORT",
        "N8N_RUNNERS_HEALTH_CHECK_SERVER_HOST",
        "N8N_SENTRY_DSN",
        "N8N_VERSION",
        "ENVIRONMENT",
        "DEPLOYMENT_NAME"
      ],
      "env-overrides": {
        "PYTHONPATH": "/opt/runners/task-runner-python",
        "PYTHONUNBUFFERED": "1",
        "N8N_RUNNERS_HEALTH_CHECK_SERVER_HOST": "0.0.0.0",
        "N8N_RUNNERS_STDLIB_DENY": "os,subprocess,sys,shutil,socket,ctypes,pickle,shelve,multiprocessing,tempfile,glob,cgi,cgitb,xmlrpc",
        "N8N_RUNNERS_EXTERNAL_ALLOW": "pandas,numpy,requests,beautifulsoup4,scikit-learn,matplotlib,pillow,openpyxl,lxml,seaborn,scipy,openai,langchain,tiktoken,fastapi,uvicorn",
        "N8N_RUNNERS_BUILTINS_DENY": "exec,eval,compile,open,input,memoryview"
      }
    }
  ]
}
EOF

echo -e "${GREEN}✅ n8n-task-runners.json actualizado${NC}"
echo ""

# 5. Verificar docker-compose.yml
echo -e "${YELLOW}🔍 Paso 5: Verificando docker-compose.yml...${NC}"

# Verificar que las variables críticas estén presentes
MISSING_VARS=0

if ! grep -q "N8N_RUNNERS_BROKER_LISTEN_ADDRESS" docker-compose.yml; then
    echo -e "${RED}❌ Falta N8N_RUNNERS_BROKER_LISTEN_ADDRESS en docker-compose.yml${NC}"
    MISSING_VARS=1
fi

if ! grep -q "N8N_RUNNERS_TASK_BROKER_URI" docker-compose.yml; then
    echo -e "${RED}❌ Falta N8N_RUNNERS_TASK_BROKER_URI en docker-compose.yml${NC}"
    MISSING_VARS=1
fi

if [ $MISSING_VARS -eq 1 ]; then
    echo ""
    echo -e "${YELLOW}⚠️  Tu docker-compose.yml necesita actualizaciones manuales.${NC}"
    echo ""
    echo "Añade estas variables en el servicio 'n8n':"
    echo ""
    echo "      - N8N_RUNNERS_BROKER_LISTEN_ADDRESS=0.0.0.0"
    echo "      - N8N_RUNNERS_BROKER_PORT=5679"
    echo ""
    echo "Y en el servicio 'n8n-runner':"
    echo ""
    echo "      - N8N_RUNNERS_TASK_BROKER_URI=ws://n8n:5679"
    echo "      - N8N_RUNNERS_HEALTH_CHECK_SERVER_ENABLED=true"
    echo "      - N8N_RUNNERS_HEALTH_CHECK_SERVER_HOST=0.0.0.0"
    echo "      - N8N_RUNNERS_HEALTH_CHECK_SERVER_PORT=5680"
    echo "      - PYTHONUNBUFFERED=1"
    echo ""
    if ! confirm "¿Has hecho estos cambios y quieres continuar?"; then
        echo "Por favor actualiza docker-compose.yml y vuelve a ejecutar este script."
        exit 1
    fi
else
    echo -e "${GREEN}✅ docker-compose.yml parece estar correcto${NC}"
fi

echo ""

# 6. Detener servicios
echo -e "${YELLOW}🛑 Paso 6: Deteniendo servicios...${NC}"
docker compose down n8n-runner n8n || true
echo -e "${GREEN}✅ Servicios detenidos${NC}"
echo ""

# 7. Reconstruir imagen
echo -e "${YELLOW}🔨 Paso 7: Reconstruyendo imagen del runner (esto puede tardar varios minutos)...${NC}"
docker compose build --no-cache n8n-runner

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Imagen reconstruida exitosamente${NC}"
else
    echo -e "${RED}❌ Error al reconstruir la imagen${NC}"
    exit 1
fi
echo ""

# 8. Iniciar servicios
echo -e "${YELLOW}🚀 Paso 8: Iniciando servicios...${NC}"

# Asegurarse de que postgres está corriendo
docker compose up -d postgres
echo "Esperando a que PostgreSQL esté listo..."
sleep 10

# Iniciar n8n
docker compose up -d n8n
echo "Esperando a que n8n esté listo..."
sleep 15

# Iniciar runner
docker compose up -d n8n-runner
echo "Esperando a que el runner esté listo..."
sleep 10

echo -e "${GREEN}✅ Servicios iniciados${NC}"
echo ""

# 9. Verificar
echo -e "${YELLOW}🔍 Paso 9: Verificando instalación...${NC}"
echo ""

# Verificar versión de websockets
echo "Verificando versión de websockets..."
WS_VERSION=$(docker exec n8n-runner /home/runner/custom-venv/bin/python -c "import websockets; print(websockets.__version__)" 2>&1)
if [[ $WS_VERSION =~ ^[0-9]+\.[0-9]+ ]]; then
    MAJOR=$(echo "$WS_VERSION" | cut -d. -f1)
    if [ "$MAJOR" -lt 13 ]; then
        echo -e "${GREEN}✅ websockets versión: $WS_VERSION (compatible)${NC}"
    else
        echo -e "${RED}❌ websockets versión: $WS_VERSION (incompatible)${NC}"
    fi
else
    echo -e "${RED}❌ No se pudo verificar versión de websockets${NC}"
fi

echo ""
echo "Últimas 30 líneas de logs del runner:"
echo "=================================================="
docker logs n8n-runner --tail 30 2>&1
echo "=================================================="
echo ""

# Verificar si hay errores de conexión
if docker logs n8n-runner 2>&1 | grep -q "additional_headers"; then
    echo -e "${RED}❌ ERROR: Todavía se detecta el error de additional_headers${NC}"
    echo "   Puede que necesites limpiar las imágenes antiguas:"
    echo "   docker system prune -a"
    exit 1
elif docker logs n8n-runner 2>&1 | grep -q "Connected:"; then
    echo -e "${GREEN}✅ Runner conectado exitosamente al broker${NC}"
else
    echo -e "${YELLOW}⚠️  No se detectó conexión confirmada en los logs${NC}"
    echo "   Espera 30 segundos más y verifica con:"
    echo "   docker logs n8n-runner 2>&1 | grep -i connected"
fi

echo ""
echo -e "${BLUE}=================================================="
echo "✅ Proceso completado"
echo -e "==================================================${NC}"
echo ""
echo "📋 Siguientes pasos:"
echo ""
echo "1. Verifica los logs en tiempo real:"
echo "   docker compose logs -f n8n-runner"
echo ""
echo "2. Si todo está correcto, deberías ver:"
echo "   - 'Connected: ws://n8n:5679/runners/_ws?id=...'"
echo "   - '-> Sent message \`runner:info\`'"
echo "   - '<- Received message \`broker:runnerregistered\`'"
echo ""
echo "3. Los backups están en: $BACKUP_DIR"
echo ""
echo "4. Documentación completa en los artifacts creados por Claude"
echo ""
echo -e "${GREEN}¡Buena suerte! 🚀${NC}"
