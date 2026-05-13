#!/bin/bash

# Script para pre-descargar modelos de Whisper usando descarga directa

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

echo -e "${BLUE}╔═══════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Whisper Model Downloader                    ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════╝${NC}"
echo ""

# Leer modelo del .env o usar default
if [ -f .env ]; then
    MODEL=$(grep "^WHISPER_MODEL=" .env | cut -d'=' -f2)
fi
MODEL=${MODEL:-base.en}

# Verificar si se pasó un modelo como argumento
if [ -n "$1" ]; then
    MODEL="$1"
fi

print_info "Modelo a descargar: $MODEL"
echo ""

# Información de modelos
case "$MODEL" in
    tiny.en|tiny)
        SIZE="75 MB"
        MEMORY="~273 MB"
        ;;
    base.en|base)
        SIZE="142 MB"
        MEMORY="~388 MB"
        ;;
    small.en|small)
        SIZE="466 MB"
        MEMORY="~852 MB"
        ;;
    medium.en|medium)
        SIZE="1.5 GB"
        MEMORY="~2.1 GB"
        ;;
    large-v1|large-v2|large-v3|large-v3-turbo)
        SIZE="2.9 GB"
        MEMORY="~3.9 GB"
        ;;
    *)
        print_warning "Modelo desconocido: $MODEL"
        SIZE="Desconocido"
        MEMORY="Desconocido"
        ;;
esac

echo "📊 Información del modelo:"
echo "   • Tamaño descarga: $SIZE"
echo "   • Memoria en uso: $MEMORY"
echo ""

# Volumen Docker
VOLUME_NAME="ai-stack-secure_whisper_models"
print_info "Volumen Docker: $VOLUME_NAME"

# Crear volumen si no existe
docker volume create $VOLUME_NAME > /dev/null 2>&1

# Verificar si el archivo existe
print_info "Verificando modelo existente..."
MODEL_EXISTS=$(docker run --rm -v $VOLUME_NAME:/models alpine \
    sh -c "[ -f /models/ggml-${MODEL}.bin ] && echo 'yes' || echo 'no'")

if [ "$MODEL_EXISTS" = "yes" ]; then
    FILE_SIZE=$(docker run --rm -v $VOLUME_NAME:/models alpine \
        ls -lh /models/ggml-${MODEL}.bin | awk '{print $5}')
    
    print_success "El modelo ya existe (Tamaño: $FILE_SIZE)"
    echo ""
    echo -n "¿Quieres re-descargarlo? (s/N): "
    read -r response
    if [[ ! "$response" =~ ^[sS]$ ]]; then
        print_info "Usando modelo existente"
        echo ""
        echo "Para iniciar los servicios ejecuta:"
        echo "  ${GREEN}./start.sh --voice${NC}"
        exit 0
    fi
    
    # Eliminar el modelo existente
    docker run --rm -v $VOLUME_NAME:/models alpine rm /models/ggml-${MODEL}.bin
    print_info "Modelo anterior eliminado"
fi

echo ""
print_info "Iniciando descarga del modelo..."
print_info "Esto puede tomar varios minutos..."
echo ""

# URL de descarga
HUGGINGFACE_URL="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-${MODEL}.bin"

echo "📥 Descargando desde HuggingFace..."
echo "   Modelo: $MODEL"
echo "   URL: $HUGGINGFACE_URL"
echo ""

# Descargar usando Alpine con curl
docker run --rm -v $VOLUME_NAME:/models alpine sh -c "
  apk add --no-cache curl > /dev/null 2>&1 &&
  cd /models &&
  curl -L --progress-bar -o ggml-${MODEL}.bin $HUGGINGFACE_URL
"

DOWNLOAD_STATUS=$?

echo ""

# Verificar que la descarga fue exitosa
if [ $DOWNLOAD_STATUS -eq 0 ]; then
    print_info "Verificando descarga..."
    
    # Verificar que el archivo existe y tiene tamaño > 0
    FILE_CHECK=$(docker run --rm -v $VOLUME_NAME:/models alpine \
        sh -c "if [ -f /models/ggml-${MODEL}.bin ] && [ -s /models/ggml-${MODEL}.bin ]; then echo 'ok'; else echo 'fail'; fi")
    
    if [ "$FILE_CHECK" = "ok" ]; then
        print_success "¡Modelo descargado exitosamente!"
        echo ""
        
        # Mostrar información del archivo
        print_info "Detalles del modelo:"
        docker run --rm -v $VOLUME_NAME:/models alpine ls -lh /models/ggml-${MODEL}.bin
        
        echo ""
        print_success "El modelo está listo para usar"
        echo ""
        echo "Ahora puedes iniciar los servicios con:"
        echo "  ${GREEN}./start.sh --voice${NC}"
        echo ""
        echo "O verificar el contenido del volumen con:"
        echo "  ${GREEN}./inspect_volumes.sh${NC}"
    else
        print_error "El archivo se descargó pero parece estar corrupto o vacío"
        echo ""
        echo "Contenido del volumen:"
        docker run --rm -v $VOLUME_NAME:/models alpine ls -lah /models/
        exit 1
    fi
else
    print_error "Error al descargar el modelo"
    echo ""
    echo "Posibles soluciones:"
    echo "  1. Verifica tu conexión a internet"
    echo "  2. Verifica que Docker esté funcionando: docker ps"
    echo "  3. Intenta con otro modelo: $0 tiny.en"
    echo "  4. Descarga manualmente:"
    echo "     curl -L -o model.bin $HUGGINGFACE_URL"
    echo ""
    echo "Contenido actual del volumen:"
    docker run --rm -v $VOLUME_NAME:/models alpine ls -lah /models/
    exit 1
fi

echo ""
print_info "📚 Modelos disponibles:"
echo ""
echo "   Para inglés (más precisos):"
echo "   • tiny.en       (75 MB)   - Más rápido, menor precisión"
echo "   • base.en       (142 MB)  - ⭐ Recomendado para GPU"
echo "   • small.en      (466 MB)  - Buen balance"
echo "   • medium.en     (1.5 GB)  - Alta precisión"
echo ""
echo "   Multiidioma:"
echo "   • tiny          (75 MB)   - Más rápido, menor precisión"
echo "   • base          (142 MB)  - Balance"
echo "   • small         (466 MB)  - Buen balance"
echo "   • medium        (1.5 GB)  - Alta precisión"
echo "   • large-v3      (2.9 GB)  - Máxima precisión"
echo ""

print_info "💡 Para descargar otro modelo:"
echo "   ./download_models.sh tiny.en"
echo "   ./download_models.sh small.en"
echo ""