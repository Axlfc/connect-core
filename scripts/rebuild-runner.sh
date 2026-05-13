#!/bin/bash

# Rebuild N8N Runner with Fixed Dependencies
# This script rebuilds the n8n-runner container with the correct websockets version

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

print_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
print_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }
print_step() { echo -e "${BLUE}[STEP]${NC} $1"; }

echo "=================================================================="
print_info "N8N Runner Rebuild Script"
echo "=================================================================="
echo ""

# Step 1: Backup current Dockerfile
print_step "Step 1: Backing up current Dockerfile.runners..."
if [ -f "Dockerfile.runners" ]; then
    cp Dockerfile.runners Dockerfile.runners.backup.$(date +%Y%m%d_%H%M%S)
    print_info "Backup created"
else
    print_error "Dockerfile.runners not found!"
    exit 1
fi

# Step 2: Update Dockerfile
print_step "Step 2: Updating Dockerfile.runners..."
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

# ⚠️ CRITICAL FIX: Install websockets 13.1+ for asyncio support
RUN /home/runner/custom-venv/bin/pip install --no-cache-dir \
    websockets==13.1 \
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

# Verify websockets.asyncio is available
RUN /home/runner/custom-venv/bin/python -c "import websockets.asyncio; print('✅ websockets.asyncio available')"
EOF

print_info "Dockerfile.runners updated with websockets==13.1"

# Step 3: Stop current runner
print_step "Step 3: Stopping current n8n-runner container..."
docker compose stop n8n-runner || true
print_info "Container stopped"

# Step 4: Remove old image (optional but recommended)
print_step "Step 4: Removing old runner image..."
docker rmi n8nio/runners:custom 2>/dev/null || print_warn "No old image to remove (this is fine)"

# Step 5: Rebuild the image
print_step "Step 5: Building new runner image..."
echo ""
print_warn "This may take 5-10 minutes depending on your system..."
echo ""

docker compose build n8n-runner

if [ $? -eq 0 ]; then
    print_info "✅ Build successful!"
else
    print_error "Build failed!"
    exit 1
fi

# Step 6: Start the runner
print_step "Step 6: Starting n8n-runner..."
docker compose up -d n8n-runner

# Wait for startup
sleep 5

# Step 7: Verify
print_step "Step 7: Verifying runner status..."
echo ""
echo "Container status:"
docker compose ps n8n-runner
echo ""

# Check logs for errors
print_info "Recent logs (checking for errors)..."
docker compose logs --tail=30 n8n-runner | grep -E "(ERROR|error|websockets.asyncio)" || print_info "No errors found! ✅"

echo ""
echo "=================================================================="
print_info "✅ Rebuild Complete!"
echo "=================================================================="
echo ""
echo "Next steps:"
echo "1. Monitor logs: docker compose logs -f n8n-runner"
echo "2. Check connection to n8n:"
echo "   docker compose logs n8n-runner | grep 'Connected'"
echo ""
echo "If you see 'Connected: ws://n8n:5679/runners/_ws' then it's working!"
echo ""
echo "To verify Python runner works, check that it registers:"
echo "   docker compose logs n8n | grep 'Registered runner'"
echo ""
