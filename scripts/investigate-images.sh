#!/bin/bash
#
# Script rápido para investigar versiones de imágenes disponibles
# sin hacer pull (usa curl y API de registros)
#

set -e

check_docker_hub_tags() {
    local image=$1
    local repo=$2
    echo "Investigando $image en Docker Hub..."
    
    # API de Docker Hub para obtener tags
    local url="https://hub.docker.com/v2/repositories/$repo/tags/?page_size=20"
    
    curl -s "$url" | grep -o '"name":"[^"]*"' | cut -d'"' -f4 | head -10
}

check_quay_tags() {
    local repo=$1
    echo "Investigando $repo en Quay.io..."
    
    local url="https://quay.io/api/v1/repository/$repo/tag/?limit=20"
    
    curl -s "$url" | grep -o '"name":"[^"]*"' | cut -d'"' -f4 | head -10
}

check_nvidia_ngc_pytorch() {
    echo "Investigando pytorch en NVIDIA NGC..."
    
    # Listar últimas versiones conocidas
    echo "Versiones conocidas disponibles:"
    echo "  - 24.12-py3 (estable actual, Jan 2026)"
    echo "  - 24.11-py3"
    echo "  - 24.10-py3"
    echo "  - 24.09-py3"
    echo ""
    echo "❌ Versión 25.01-py3 NO existe (es futura)"
}

echo "📦 Investigación de Versiones de Imágenes"
echo ""

# Investigar LibreTranslate
echo "=== LibreTranslate ==="
if command -v curl &> /dev/null; then
    check_docker_hub_tags "libretranslate/libretranslate" "libretranslate/libretranslate" 2>/dev/null || echo "No se pudo conectar a Docker Hub"
else
    echo "curl no disponible, saltando verificación"
fi
echo ""

# Investigar Ollama
echo "=== Ollama ==="
if command -v curl &> /dev/null; then
    check_docker_hub_tags "ollama/ollama" "ollama/ollama" 2>/dev/null || echo "No se pudo conectar a Docker Hub"
else
    echo "curl no disponible"
fi
echo ""

# Investigar Qdrant
echo "=== Qdrant ==="
if command -v curl &> /dev/null; then
    check_docker_hub_tags "qdrant/qdrant" "qdrant/qdrant" 2>/dev/null || echo "No se pudo conectar a Docker Hub"
else
    echo "curl no disponible"
fi
echo ""

# NVIDIA PyTorch (no tiene API pública fácil)
echo "=== NVIDIA PyTorch ==="
check_nvidia_ngc_pytorch
echo ""

# LanguageTool
echo "=== LanguageTool ==="
if command -v curl &> /dev/null; then
    check_docker_hub_tags "erikvl87/languagetool" "erikvl87/languagetool" 2>/dev/null || echo "No se pudo conectar a Docker Hub"
else
    echo "curl no disponible"
fi
