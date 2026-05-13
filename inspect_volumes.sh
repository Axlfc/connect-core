#!/bin/bash

# Script para inspeccionar los volúmenes de Docker del proyecto

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

print_header() {
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║  $1"
    echo -e "${CYAN}╚══════════════════════════════════════════════╝${NC}"
    echo ""
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_header "Docker Volumes Inspector - AI Stack"

# Volúmenes del proyecto
VOLUMES=(
    "ai-stack-secure_whisper_models:Whisper Models"
    "ai-stack-secure_kokoro_models:Kokoro Models"
    "ai-stack-secure_ollama_storage:Ollama Models"
    "ai-stack-secure_n8n_storage:n8n Data"
    "ai-stack-secure_postgres_storage:PostgreSQL Data"
    "ai-stack-secure_qdrant_storage:Qdrant Vectors"
    "ai-stack-secure_redis_data:Redis Data"
    "ai-stack-secure_matrix_data:Matrix Data"
    "ai-stack-secure_matrix_postgres:Matrix PostgreSQL"
)

echo "🔍 Inspeccionando volúmenes del proyecto..."
echo ""

for volume_info in "${VOLUMES[@]}"; do
    IFS=':' read -r volume_name description <<< "$volume_info"
    
    # Verificar si el volumen existe
    if docker volume inspect "$volume_name" > /dev/null 2>&1; then
        echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${BLUE}📦 $description${NC}"
        echo -e "   Volume: ${YELLOW}$volume_name${NC}"
        
        # Obtener tamaño del volumen
        MOUNTPOINT=$(docker volume inspect "$volume_name" --format '{{.Mountpoint}}' 2>/dev/null)
        if [ -n "$MOUNTPOINT" ] && [ -d "$MOUNTPOINT" ]; then
            SIZE=$(sudo du -sh "$MOUNTPOINT" 2>/dev/null | cut -f1 || echo "N/A")
            echo "   Tamaño: $SIZE"
        fi
        
        # Listar contenido
        echo "   Contenido:"
        docker run --rm -v "$volume_name:/data" alpine \
            sh -c "ls -lah /data 2>/dev/null | tail -n +2 | head -20" | \
            sed 's/^/      /'
        
        # Contar archivos
        FILE_COUNT=$(docker run --rm -v "$volume_name:/data" alpine \
            sh -c "find /data -type f 2>/dev/null | wc -l")
        DIR_COUNT=$(docker run --rm -v "$volume_name:/data" alpine \
            sh -c "find /data -type d 2>/dev/null | wc -l")
        echo "   Estadísticas: $FILE_COUNT archivos, $DIR_COUNT directorios"
        echo ""
    else
        echo -e "${YELLOW}⚠️  $description${NC}"
        echo -e "   Volume: ${YELLOW}$volume_name${NC}"
        echo "   Estado: No existe (se creará al iniciar los servicios)"
        echo ""
    fi
done

# Whisper específico
print_header "Análisis Detallado - Whisper Models"

WHISPER_VOLUME="ai-stack-secure_whisper_models"
if docker volume inspect "$WHISPER_VOLUME" > /dev/null 2>&1; then
    print_info "Buscando modelos de Whisper..."
    
    MODELS=$(docker run --rm -v "$WHISPER_VOLUME:/data" alpine \
        find /data -name "ggml-*.bin" -type f 2>/dev/null)
    
    if [ -n "$MODELS" ]; then
        echo ""
        echo "Modelos encontrados:"
        echo "$MODELS" | while read -r model; do
            SIZE=$(docker run --rm -v "$WHISPER_VOLUME:/data" alpine \
                ls -lh "$model" 2>/dev/null | awk '{print $5}')
            BASENAME=$(basename "$model")
            echo "  • $BASENAME ($SIZE)"
        done
    else
        echo ""
        echo -e "${YELLOW}⚠️  No se encontraron modelos de Whisper${NC}"
        echo ""
        echo "Para descargar un modelo ejecuta:"
        echo "  ${GREEN}./download_models.sh base.en${NC}"
    fi
    
    # Mostrar todo el contenido del volumen
    echo ""
    print_info "Contenido completo del volumen:"
    docker run --rm -v "$WHISPER_VOLUME:/data" alpine \
        sh -c "cd /data && find . -ls 2>/dev/null | head -50" | \
        sed 's/^/  /'
else
    print_info "El volumen de Whisper no existe todavía"
    echo "Se creará automáticamente al ejecutar ./download_models.sh o ./start.sh --voice"
fi

# Ollama específico
print_header "Análisis Detallado - Ollama Models"

OLLAMA_VOLUME="ai-stack-secure_ollama_storage"
if docker volume inspect "$OLLAMA_VOLUME" > /dev/null 2>&1; then
    print_info "Buscando modelos de Ollama..."
    
    OLLAMA_MODELS=$(docker run --rm -v "$OLLAMA_VOLUME:/data" alpine \
        sh -c "find /data -name 'manifest' 2>/dev/null | wc -l")
    
    if [ "$OLLAMA_MODELS" -gt 0 ]; then
        echo ""
        echo "Modelos de Ollama: $OLLAMA_MODELS encontrados"
        
        # Listar modelos
        docker run --rm -v "$OLLAMA_VOLUME:/data" alpine \
            sh -c "find /data/models/manifests -type f 2>/dev/null" | \
            sed 's|.*/manifests/registry.ollama.ai/library/||' | \
            sed 's/^/  • /'
    else
        echo ""
        echo -e "${YELLOW}⚠️  No se encontraron modelos de Ollama${NC}"
        echo "Los modelos se descargan automáticamente al iniciar"
    fi
else
    print_info "El volumen de Ollama no existe todavía"
fi

# Resumen final
print_header "Comandos Útiles"

echo "Inspeccionar un volumen específico:"
echo "  ${GREEN}docker run --rm -v VOLUME_NAME:/data alpine ls -lah /data${NC}"
echo ""
echo "Limpiar un volumen específico:"
echo "  ${YELLOW}docker volume rm VOLUME_NAME${NC}"
echo ""
echo "Limpiar TODOS los volúmenes (⚠️  PELIGROSO):"
echo "  ${RED}./stop.sh --volumes${NC}"
echo ""
echo "Hacer backup de un volumen:"
echo "  ${GREEN}docker run --rm -v VOLUME_NAME:/data -v \$(pwd):/backup alpine tar czf /backup/volume-backup.tar.gz -C /data .${NC}"
echo ""
echo "Restaurar backup de un volumen:"
echo "  ${GREEN}docker run --rm -v VOLUME_NAME:/data -v \$(pwd):/backup alpine tar xzf /backup/volume-backup.tar.gz -C /data${NC}"
echo ""

print_header "Espacio en Disco"

echo "Uso de Docker:"
docker system df
echo ""

print_info "Para liberar espacio:"
echo "  docker system prune -a --volumes  (⚠️  elimina todo lo no usado)"
echo ""
