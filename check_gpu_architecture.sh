#!/bin/bash

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }

print_header "DIAGNÓSTICO DE GPU Y CUDA"

# 1. Verificar nvidia-smi
if ! command -v nvidia-smi &> /dev/null; then
    print_error "nvidia-smi no encontrado"
    echo "Instala los drivers NVIDIA primero"
    exit 1
fi

print_success "nvidia-smi encontrado"
echo ""

# 2. Información de GPU
print_info "Información de GPU:"
nvidia-smi --query-gpu=name,driver_version,memory.total,compute_cap --format=csv,noheader

echo ""

# 3. Detalles completos
print_header "DETALLES DE GPU"
nvidia-smi

echo ""

# 4. Compute Capability (arquitectura)
print_header "COMPUTE CAPABILITY"
GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)
COMPUTE_CAP=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader | head -1)

echo "GPU: $GPU_NAME"
echo "Compute Capability: $COMPUTE_CAP"
echo ""

# Explicar la arquitectura
print_info "Explicación de Compute Capability:"
case ${COMPUTE_CAP} in
    8.9)
        ARCH="Ada Lovelace (RTX 40 series)"
        MIN_CUDA="11.8"
        ;;
    8.6)
        ARCH="Ampere (RTX 30 series, A series)"
        MIN_CUDA="11.1"
        ;;
    8.0)
        ARCH="Ampere (A100)"
        MIN_CUDA="11.0"
        ;;
    7.5)
        ARCH="Turing (RTX 20 series, GTX 16 series)"
        MIN_CUDA="10.0"
        ;;
    7.0)
        ARCH="Volta (Tesla V100)"
        MIN_CUDA="9.0"
        ;;
    6.1)
        ARCH="Pascal (GTX 10 series)"
        MIN_CUDA="8.0"
        ;;
    *)
        ARCH="Desconocida"
        MIN_CUDA="Desconocido"
        ;;
esac

echo "  Arquitectura: $ARCH"
echo "  CUDA mínimo requerido: $MIN_CUDA"
echo ""

# 5. Versión de CUDA
print_header "VERSIÓN DE CUDA"
DRIVER_VERSION=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1)
echo "Driver NVIDIA: $DRIVER_VERSION"

# Extraer versión máxima de CUDA soportada
if nvidia-smi | grep -q "CUDA Version:"; then
    CUDA_VERSION=$(nvidia-smi | grep "CUDA Version:" | awk '{print $9}')
    echo "CUDA Version máxima soportada: $CUDA_VERSION"
else
    print_warning "No se pudo detectar versión CUDA"
fi

echo ""

# 6. Probar Docker + GPU
print_header "PRUEBA DE DOCKER + GPU"

print_info "Probando acceso a GPU desde Docker..."
docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu22.04 nvidia-smi &> /tmp/docker_gpu_test.log

if [ $? -eq 0 ]; then
    print_success "Docker puede acceder a la GPU"
    echo ""
    cat /tmp/docker_gpu_test.log
else
    print_error "Docker NO puede acceder a la GPU"
    echo "Error:"
    cat /tmp/docker_gpu_test.log
    echo ""
    print_warning "Instala nvidia-container-toolkit:"
    echo "  sudo apt-get install nvidia-container-toolkit"
    echo "  sudo systemctl restart docker"
fi

echo ""

# 7. Verificar qué imágenes necesitas
print_header "RECOMENDACIONES PARA TU GPU"

echo "GPU Detectada: $GPU_NAME"
echo "Compute Capability: $COMPUTE_CAP"
echo "Arquitectura: $ARCH"
echo ""

print_info "Para que funcionen las imágenes GPU necesitas:"
echo ""
echo "1. WHISPER (onerahmet/openai-whisper-asr-webservice)"
echo "   • Imagen GPU: onerahmet/openai-whisper-asr-webservice:latest-gpu"
echo "   • Esta imagen usa PyTorch con CUDA"
echo "   • Compute Cap mínima: 6.1 (Pascal)"
echo ""

if (( $(echo "$COMPUTE_CAP >= 6.1" | bc -l) )); then
    print_success "Tu GPU es compatible con Whisper GPU"
else
    print_error "Tu GPU NO es compatible (compute cap < 6.1)"
fi

echo ""
echo "2. KOKORO (ghcr.io/remsky/kokoro-fastapi-gpu)"
echo "   • Esta imagen usa PyTorch con CUDA"
echo "   • Compute Cap mínima: 6.1 (Pascal)"
echo ""

if (( $(echo "$COMPUTE_CAP >= 6.1" | bc -l) )); then
    print_success "Tu GPU es compatible con Kokoro GPU"
else
    print_error "Tu GPU NO es compatible (compute cap < 6.1)"
fi

echo ""

# 8. Diagnóstico del error actual
print_header "DIAGNÓSTICO DEL ERROR"

print_info "El error 'no kernel image is available' puede deberse a:"
echo ""
echo "1. ❌ La imagen fue compilada para una arquitectura más nueva"
echo "   Solución: Usar versión CPU o compilar imagen custom"
echo ""
echo "2. ❌ Driver NVIDIA desactualizado"
echo "   Solución: Actualizar driver"
echo "   Recomendado: ≥ 525.x para CUDA 12.x"
echo ""
echo "3. ❌ CUDA Toolkit en la imagen es incompatible"
echo "   Solución: Usar imagen con CUDA compatible"
echo ""

# 9. Verificar drivers
print_header "VERIFICACIÓN DE DRIVERS"

CURRENT_DRIVER=$(echo "$DRIVER_VERSION" | cut -d. -f1)
print_info "Driver actual: $DRIVER_VERSION"

if [ "$CURRENT_DRIVER" -ge 525 ]; then
    print_success "Driver es reciente (≥525.x) - compatible con CUDA 12.x"
elif [ "$CURRENT_DRIVER" -ge 470 ]; then
    print_warning "Driver intermedio (470-524.x) - compatible con CUDA 11.x"
    echo "   Considera actualizar a ≥525.x para CUDA 12.x"
else
    print_error "Driver antiguo (<470.x)"
    echo "   DEBES actualizar el driver"
fi

echo ""

# 10. Conclusión y próximos pasos
print_header "CONCLUSIÓN Y PRÓXIMOS PASOS"

echo "Tu configuración:"
echo "  • GPU: $GPU_NAME"
echo "  • Compute Cap: $COMPUTE_CAP ($ARCH)"
echo "  • Driver: $DRIVER_VERSION"
echo "  • CUDA Max: ${CUDA_VERSION:-Desconocido}"
echo ""

if (( $(echo "$COMPUTE_CAP >= 6.1" | bc -l) )) && [ "$CURRENT_DRIVER" -ge 470 ]; then
    print_success "Tu GPU DEBERÍA ser compatible"
    echo ""
    echo "El problema probablemente es:"
    echo "  1. Las imágenes Docker usan CUDA 12.x pero tu driver soporta CUDA 11.x"
    echo "  2. Las imágenes fueron compiladas para compute cap > $COMPUTE_CAP"
    echo ""
    print_info "Opciones:"
    echo ""
    echo "A) Actualizar driver NVIDIA (RECOMENDADO)"
    echo "   sudo apt-get update"
    echo "   sudo apt-get install nvidia-driver-535"
    echo "   sudo reboot"
    echo ""
    echo "B) Usar imágenes con CUDA 11.x en lugar de 12.x"
    echo "   Modificar docker-compose.yml para usar tags :cuda11"
    echo ""
    echo "C) Quedarte con CPU (funciona bien para uso normal)"
    echo "   Ya está configurado y funcionando"
else
    print_warning "Tu GPU puede tener limitaciones"
    echo ""
    if (( $(echo "$COMPUTE_CAP < 6.1" | bc -l) )); then
        print_error "GPU muy antigua (compute cap < 6.1)"
        echo "  Recomendación: Usar versión CPU"
    fi
    
    if [ "$CURRENT_DRIVER" -lt 470 ]; then
        print_error "Driver muy antiguo"
        echo "  Recomendación: Actualizar driver a ≥525.x"
    fi
fi

echo ""
print_info "¿Quieres intentar arreglar la GPU? Ejecuta:"
echo "  ./fix_gpu_compatibility.sh"
echo ""
