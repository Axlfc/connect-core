#!/bin/bash

# Script para preparar Whisper antes de iniciar los servicios
# Descarga el modelo con acceso a internet, antes de que el contenedor se levante

set -e

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════${NC}"
    echo ""
}

print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }

print_header "Whisper STT Setup"

# Crear directorio para volumen de modelos
print_info "Creating model cache directory..."
mkdir -p "${HOME}/.cache/whisper"
print_success "Model cache ready at ${HOME}/.cache/whisper"

echo ""

# Detectar internet
print_info "Checking internet connectivity..."
if ping -c 1 8.8.8.8 &> /dev/null 2>&1; then
    print_success "Internet available"
    HAS_INTERNET=true
else
    print_warning "No internet detected"
    print_warning "You'll need to pre-download models manually"
    HAS_INTERNET=false
fi

echo ""

# Verificar Python
print_info "Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    print_error "Python3 not found"
    echo "Install with: sudo apt-get install python3 python3-pip"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
print_success "Python $PYTHON_VERSION found"

echo ""

# Verificar/instalar openai-whisper
print_info "Checking openai-whisper..."
if python3 -c "import whisper" 2>/dev/null; then
    WHISPER_VERSION=$(python3 -c "import whisper; print(whisper.__version__)" 2>/dev/null || echo "unknown")
    print_success "openai-whisper already installed (version: $WHISPER_VERSION)"
else
    if [ "$HAS_INTERNET" = true ]; then
        print_info "Installing openai-whisper..."
        if python3 -m pip install --user openai-whisper &> /dev/null; then
            print_success "openai-whisper installed"
        else
            print_error "Failed to install openai-whisper"
            echo "Try manually: pip3 install openai-whisper"
            exit 1
        fi
    else
        print_error "openai-whisper not found and no internet to install"
        exit 1
    fi
fi

echo ""

# Modelos a descargar
MODELS=(
    "tiny.en"
    "base.en"
)

print_header "Model Download"

if [ "$HAS_INTERNET" = false ]; then
    print_warning "Skipping model download (no internet)"
    echo "You need to manually download models using:"
    echo "  python3 -c \"import whisper; whisper.load_model('base.en')\""
    exit 0
fi

print_info "The following models will be downloaded (if not present):"
for MODEL in "${MODELS[@]}"; do
    echo "  • $MODEL"
done

echo ""

# Descargar modelos
for MODEL in "${MODELS[@]}"; do
    MODEL_PATH="${HOME}/.cache/whisper/ggml-${MODEL}.bin"
    
    # OpenAI Whisper descarga a un archivo diferente
    if [ -d "${HOME}/.cache/whisper" ]; then
        # Contar archivos para el modelo
        EXISTING=$(find "${HOME}/.cache/whisper" -name "*${MODEL}*" 2>/dev/null | wc -l)
        if [ $EXISTING -gt 0 ]; then
            SIZE=$(du -sh "${HOME}/.cache/whisper" 2>/dev/null | awk '{print $1}')
            print_success "Model '$MODEL' already downloaded (cache: $SIZE)"
            continue
        fi
    fi
    
    print_info "Downloading model: $MODEL"
    echo "  (This may take a few minutes...)"
    
    if python3 << PYTHON_SCRIPT 2>&1
import whisper
import sys
import os

os.environ['PYTORCH_ENABLE_MPS_FALLBACK'] = '1'

try:
    model = whisper.load_model("$MODEL")
    print(f"✓ Model '$MODEL' downloaded successfully")
except Exception as e:
    print(f"✗ Failed to download '$MODEL': {e}")
    sys.exit(1)
PYTHON_SCRIPT
    then
        print_success "Downloaded: $MODEL"
    else
        print_error "Failed to download: $MODEL"
        echo ""
        echo "You can retry manually:"
        echo "  python3 -c \"import whisper; whisper.load_model('$MODEL')\""
    fi
    
    echo ""
done

echo ""

# Mostrar cache
print_info "Model cache contents:"
if [ -d "${HOME}/.cache/whisper" ]; then
    du -sh "${HOME}/.cache/whisper"/* 2>/dev/null | sed 's/^/  /'
else
    print_warning "Cache directory not found"
fi

echo ""

print_header "Setup Complete"
print_success "Whisper is ready!"
echo ""
print_info "Next steps:"
echo "  1. Start the services: ./start.sh"
echo "  2. Monitor logs: docker logs -f whisper-stt"
echo "  3. Test the API: curl http://localhost:9001/health"
echo ""
