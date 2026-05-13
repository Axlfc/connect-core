#!/bin/bash

# quick-fix-tini.sh - Solución rápida para el error de tini
set -e

echo "🔧 Corrigiendo error de tini en n8n-runner..."
echo ""

# 1. Detener el contenedor
echo "1️⃣  Deteniendo n8n-runner..."
docker compose down n8n-runner

# 2. Verificar docker-compose.yml
echo ""
echo "2️⃣  Verificando docker-compose.yml..."

if grep -A 30 "n8n-runner:" docker-compose.yml | grep -q "command: \[\]"; then
    echo "❌ Encontrado 'command: []' que causa el problema"
    echo ""
    echo "Por favor, edita docker-compose.yml y:"
    echo "1. Busca la sección 'n8n-runner:'"
    echo "2. ELIMINA completamente la línea que dice 'command: []'"
    echo "3. Guarda el archivo"
    echo ""
    read -p "Presiona Enter cuando hayas hecho el cambio..."
else
    echo "✅ No se encuentra 'command: []' problemático"
fi

# 3. Crear Dockerfile.runners corregido
echo ""
echo "3️⃣  Actualizando Dockerfile.runners con tini..."

cat > Dockerfile.runners << 'EOF'
FROM n8nio/runners:1.121.0

USER root

# ✅ Install tini if not present (required for proper init)
RUN if ! command -v tini > /dev/null 2>&1; then \
    apk add --no-cache tini; \
    fi

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

echo "✅ Dockerfile.runners actualizado"

# 4. Reconstruir imagen
echo ""
echo "4️⃣  Reconstruyendo imagen (esto puede tardar varios minutos)..."
docker compose build --no-cache n8n-runner

if [ $? -ne 0 ]; then
    echo "❌ Error al reconstruir la imagen"
    exit 1
fi

echo "✅ Imagen reconstruida"

# 5. Iniciar n8n-runner
echo ""
echo "5️⃣  Iniciando n8n-runner..."
docker compose up -d n8n-runner

echo ""
echo "⏳ Esperando 15 segundos..."
sleep 15

# 6. Verificar
echo ""
echo "6️⃣  Verificando estado..."
echo ""

if docker ps | grep -q n8n-runner; then
    echo "✅ Contenedor n8n-runner está corriendo"
    echo ""
    echo "📋 Últimas 30 líneas de logs:"
    echo "=================================================="
    docker logs n8n-runner --tail 30
    echo "=================================================="
    echo ""
    
    # Verificar si hay errores
    if docker logs n8n-runner 2>&1 | grep -q "additional_headers"; then
        echo "❌ Todavía hay error de websockets"
    elif docker logs n8n-runner 2>&1 | grep -q "Connected:"; then
        echo "✅ Runner conectado exitosamente!"
    else
        echo "⚠️  No se detecta conexión clara aún, espera 30s más"
    fi
else
    echo "❌ Contenedor n8n-runner NO está corriendo"
    echo ""
    echo "Ver error completo:"
    docker compose logs n8n-runner
fi

echo ""
echo "✅ Script completado"
echo ""
echo "Para ver logs en tiempo real:"
echo "  docker compose logs -f n8n-runner"
