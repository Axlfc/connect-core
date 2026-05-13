#!/bin/bash
#
# Script para validar versiones de imágenes base en los Dockerfiles
# Verifica que las imágenes especificadas existan en los registros públicos
#
# Nota: Este script SOLO verifica los Dockerfiles sin hacer pull
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🔍 Validando versiones de imágenes base..."
echo ""

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

FAILED=0
PASSED=0

# Tabla de versiones conocidas como disponibles
declare -A KNOWN_VERSIONS
KNOWN_VERSIONS["nvcr.io/nvidia/pytorch:24.12-py3"]="✅ Disponible (estable)"
KNOWN_VERSIONS["nvcr.io/nvidia/pytorch:25.01-py3"]="❌ NO EXISTE (versión futura)"
KNOWN_VERSIONS["ollama/ollama:0.2.1"]="✅ Disponible"
KNOWN_VERSIONS["qdrant/qdrant:v1.9.2"]="✅ Disponible"
KNOWN_VERSIONS["libretranslate/libretranslate:1.6.1"]="⚠️  VERIFICAR (puede no estar disponible)"
KNOWN_VERSIONS["libretranslate/libretranslate:1.5.0"]="❌ NO ENCONTRADA"
KNOWN_VERSIONS["erikvl87/languagetool:6.4"]="✅ Disponible"

echo "📋 Imágenes encontradas en Dockerfiles:"
echo ""

# Extraer imágenes FROM de todos los Dockerfiles
grep -h "^FROM " "$PROJECT_ROOT"/Dockerfile* 2>/dev/null | sort -u | while read -r line; do
    image=$(echo "$line" | sed 's/^FROM //' | sed 's/ as.*//')
    
    # Saltar variables
    if [[ ! "$image" =~ \$ ]]; then
        # Verificar en tabla
        if [[ -v KNOWN_VERSIONS["$image"] ]]; then
            echo "  $image"
            echo "    ${KNOWN_VERSIONS[$image]}"
            echo ""
        else
            echo "  $image"
            echo "    ⓘ No documentada (verificar manualmente)"
            echo ""
        fi
    fi
done

echo ""
echo "=========================================="
echo "📝 ALTERNATIVAS SI HAY PROBLEMAS:"
echo "=========================================="
echo ""
echo "Si encuentras errores de 'not found' al hacer build:"
echo ""
echo "1. VERIFICAR VERSIONES REALES:"
echo "   Docker Hub: https://hub.docker.com/r/{repo}/tags"
echo "   NVIDIA NGC: https://catalog.ngc.nvidia.com/orgs/nvidia/containers/pytorch"
echo ""
echo "2. ACTUALIZAR DOCKERFILE:"
echo "   sed -i 's/VERSION_VIEJA/VERSION_NUEVA/g' Dockerfile.nombre"
echo ""
echo "3. LIMPIAR Y RECONSTRUIR:"
echo "   docker compose build --no-cache"
echo "   docker compose --profile gpu-nvidia --profile voice up -d"
echo ""
echo "=========================================="
echo "⚠️  PROBLEMAS CONOCIDOS (Jan 2026):"
echo "=========================================="
echo ""
echo "• libretranslate:1.6.1 → Verificar disponibilidad en Docker Hub"
echo "• pytorch:25.01-py3 → NO EXISTE (usar 24.12-py3)"
echo ""
echo "Si el build falla, consulta la sección de troubleshooting en .github/copilot-instructions.md"

