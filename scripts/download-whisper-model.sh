#!/bin/bash

# Script para pre-descargar modelos de Whisper antes de levantar los servicios
# Esto evita el problema de DNS/internet dentro del contenedor

set -e

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}======================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}======================================${NC}"
}

print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }

print_header "Whisper Model Pre-downloader"

# Crear directorio para modelos si no existe
mkdir -p ./shared/whisper-models

print_info "Checking internet connectivity..."
if ! ping -c 1 8.8.8.8 &> /dev/null; then
    print_warning "No internet detected - models must be pre-downloaded"
    echo "Please ensure models are available at:"
    echo "  - ./shared/whisper-models/"
    exit 1
fi

print_success "Internet available"
echo ""

# Modelos a descargar
MODELS=(
    "large-v3"
)

print_info "Checking for Python and dependencies..."
if ! command -v python3 &> /dev/null; then
    print_error "Python3 is required"
    echo "Install with: sudo apt-get install python3 python3-pip"
    exit 1
fi

# Instalar openai-whisper si no existe
if ! python3 -c "import whisper" 2>/dev/null; then
    print_info "Installing openai-whisper..."
    pip3 install --user openai-whisper
fi

print_success "Dependencies OK"
echo ""

# Descargar modelos
print_header "Downloading Whisper Models"

for MODEL in "${MODELS[@]}"; do
    echo ""
    print_info "Model: $MODEL"
    
    MODEL_FILE="./shared/whisper-models/ggml-${MODEL}.bin"
    
    if [ -f "$MODEL_FILE" ]; then
        SIZE=$(du -h "$MODEL_FILE" | cut -f1)
        print_success "Already downloaded ($SIZE)"
        continue
    fi
    
    echo "Downloading..."
    python3 << PYTHON_DOWNLOAD
import whisper
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    logger.info(f"Downloading {os.environ['MODEL']}...")
    model = whisper.load_model("${MODEL}")
    logger.info(f"✓ Downloaded successfully")
except Exception as e:
    logger.error(f"✗ Failed: {e}")
    exit(1)
PYTHON_DOWNLOAD
    
    if [ $? -eq 0 ]; then
        print_success "Downloaded: $MODEL"
    else
        print_error "Failed to download: $MODEL"
        exit 1
    fi
done

echo ""
print_header "Summary"
print_success "All models pre-downloaded!"
print_info "Models location: ./shared/whisper-models/"
echo ""
ls -lh ./shared/whisper-models/ 2>/dev/null || echo "No models found (check if download succeeded)"
echo ""
print_info "You can now start the services:"
echo "  ./start.sh"
