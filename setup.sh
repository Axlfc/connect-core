#!/bin/bash
# Cognito Stack - Script de Instalación Completo
# Para RTX 5070 12GB + Docker + Ollama

set -e  # Exit on error

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

CONTAINER_NAME="ollama-gpu"

# =============================================================================
# FUNCIONES AUXILIARES
# =============================================================================

print_header() {
    echo -e "\n${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}  $1"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}\n"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

check_command() {
    if command -v $1 &> /dev/null; then
        print_success "$1 está instalado"
        return 0
    else
        print_error "$1 NO está instalado"
        return 1
    fi
}

# =============================================================================
# 1. VERIFICACIÓN DE REQUISITOS
# =============================================================================

check_requirements() {
    print_header "VERIFICANDO REQUISITOS DEL SISTEMA"
    
    local all_ok=true
    
    # Docker
    if check_command docker; then
        docker --version
    else
        print_warning "Instala Docker: https://docs.docker.com/engine/install/"
        all_ok=false
    fi
    
    # NVIDIA Driver
    if check_command nvidia-smi; then
        nvidia-smi --query-gpu=name,driver_version --format=csv,noheader
    else
        print_error "NVIDIA Driver no detectado"
        print_info "Instala drivers: sudo ubuntu-drivers autoinstall"
        all_ok=false
    fi
    
    # Python
    if check_command python3; then
        python3 --version
    else
        print_error "Python 3 no está instalado"
        all_ok=false
    fi
    
    # Pip
    if check_command pip3; then
        pip3 --version
    else
        print_warning "pip3 no está instalado"
        print_info "Instala: sudo apt install python3-pip"
    fi
    
    if [ "$all_ok" = false ]; then
        print_error "Algunos requisitos no están cumplidos. Por favor, instálalos primero."
        exit 1
    fi
    
    print_success "Todos los requisitos están instalados"
}

# =============================================================================
# 2. VERIFICAR/CREAR CONTENEDOR OLLAMA
# =============================================================================

setup_ollama_container() {
    print_header "CONFIGURANDO CONTENEDOR OLLAMA CON GPU"
    
    # Check si el contenedor ya existe
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        print_info "Contenedor ${CONTAINER_NAME} ya existe"
        
        # Check si está corriendo
        if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
            print_success "Contenedor está corriendo"
        else
            print_warning "Contenedor existe pero no está corriendo. Iniciando..."
            docker start ${CONTAINER_NAME}
            print_success "Contenedor iniciado"
        fi
    else
        print_info "Creando nuevo contenedor ${CONTAINER_NAME}..."
        
        docker run -d \
            --gpus=all \
            --name ${CONTAINER_NAME} \
            -v ollama:/root/.ollama \
            -p 11434:11434 \
            --restart unless-stopped \
            ollama/ollama
        
        print_success "Contenedor ${CONTAINER_NAME} creado y corriendo"
        sleep 5  # Dar tiempo para que inicie
    fi
    
    # Verificar GPU en contenedor
    print_info "Verificando GPU en contenedor..."
    docker exec ${CONTAINER_NAME} nvidia-smi --query-gpu=name --format=csv,noheader
    print_success "GPU detectada en contenedor"
}

# =============================================================================
# 3. INSTALAR MODELOS ESENCIALES
# =============================================================================

install_models() {
    print_header "INSTALANDO MODELOS ESENCIALES"
    
    # Modelos ya instalados
    print_info "Verificando modelos instalados..."
    docker exec ${CONTAINER_NAME} ollama list
    
    echo ""
    read -p "¿Deseas instalar/actualizar modelos adicionales? (y/n): " install_choice
    
    if [ "$install_choice" != "y" ]; then
        print_info "Saltando instalación de modelos"
        return
    fi
    
    # Lista de modelos recomendados que NO tienes
    declare -a recommended_models=(
        # Ya tienes estos, comentados para referencia:
        # "deepseek-r1:7b"
        # "deepseek-r1:14b"
        # "deepseek-r1:32b"
        # "cogito:8b"
        # "cogito:14b"
        # "phi4:14b"
        # "qwen2.5-coder:14b"
        # "qwen2.5:7b"
        # "qwen2.5:14b"
        # "gemma3:12b"
        # "llama3.1:8b"
        # "devstral:24b"
        # "qwen3-vl:8b"
        # "gpt-oss:20b"
        
        # Modelos adicionales útiles (opcionales)
        "mistral:7b"           # Generación creativa
        "qwen2.5:32b"          # Razonamiento avanzado (si tienes espacio)
    )
    
    print_info "Modelos recomendados para instalar:"
    for model in "${recommended_models[@]}"; do
        echo "  - $model"
    done
    
    echo ""
    read -p "¿Instalar estos modelos? (y/n): " confirm
    
    if [ "$confirm" = "y" ]; then
        for model in "${recommended_models[@]}"; do
            print_info "Descargando $model..."
            docker exec ${CONTAINER_NAME} ollama pull $model
            print_success "$model instalado"
        done
    fi
}

# =============================================================================
# 4. ELIMINAR MODELOS MUY PESADOS (Opcional)
# =============================================================================

cleanup_heavy_models() {
    print_header "LIMPIEZA DE MODELOS PESADOS"
    
    print_warning "Con 12GB VRAM, modelos >20GB harán swap a RAM (muy lento)"
    print_info "Modelos pesados detectados:"
    echo "  - deepseek-r1:32b (19GB)"
    echo "  - qwen3-coder:30b (18GB)"
    echo "  - devstral:24b (14GB)"
    echo "  - gpt-oss:20b (13GB)"
    
    echo ""
    read -p "¿Deseas eliminar modelos muy pesados (>18GB)? (y/n): " cleanup_choice
    
    if [ "$cleanup_choice" = "y" ]; then
        # Opcional: eliminar los MUY pesados
        read -p "¿Eliminar deepseek-r1:32b (19GB)? (y/n): " rm_32b
        if [ "$rm_32b" = "y" ]; then
            docker exec ${CONTAINER_NAME} ollama rm deepseek-r1:32b
            print_success "deepseek-r1:32b eliminado (usa 14b en su lugar)"
        fi
        
        read -p "¿Eliminar qwen3-coder:30b (18GB)? (y/n): " rm_30b
        if [ "$rm_30b" = "y" ]; then
            docker exec ${CONTAINER_NAME} ollama rm qwen3-coder:30b
            print_success "qwen3-coder:30b eliminado (usa qwen2.5-coder:14b)"
        fi
        
        print_info "Los modelos 14B ofrecen ~90% del rendimiento con 50% del VRAM"
    fi
}

# =============================================================================
# 5. CONFIGURAR OPTIMIZACIONES
# =============================================================================

configure_optimizations() {
    print_header "CONFIGURANDO OPTIMIZACIONES PARA RTX 5070"
    
    # Detectar shell
    if [ -n "$ZSH_VERSION" ]; then
        SHELL_RC="$HOME/.zshrc"
    else
        SHELL_RC="$HOME/.bashrc"
    fi
    
    print_info "Añadiendo variables de entorno a $SHELL_RC"
    
    # Backup del archivo actual
    cp "$SHELL_RC" "${SHELL_RC}.backup_$(date +%Y%m%d_%H%M%S)"
    
    # Añadir configuración si no existe
    if ! grep -q "OLLAMA_FLASH_ATTENTION" "$SHELL_RC"; then
        cat >> "$SHELL_RC" << 'EOF'

# ============================================================
# Cognito Stack - Optimizaciones Ollama para RTX 5070 12GB
# ============================================================
export OLLAMA_FLASH_ATTENTION=1
export OLLAMA_KV_CACHE_TYPE=q8_0
export OLLAMA_NUM_GPU=999
export OLLAMA_KEEP_ALIVE=2m
export OLLAMA_MAX_LOADED_MODELS=2
export OLLAMA_NUM_CTX=16384

# Alias útiles
alias cognito-status="python3 ~/cognito-stack/monitor.py status"
alias cognito-watch="python3 ~/cognito-stack/monitor.py watch"
alias cognito-run="python3 ~/cognito-stack/cognito_agent.py"

EOF
        print_success "Optimizaciones añadidas a $SHELL_RC"
        print_info "Ejecuta: source $SHELL_RC"
    else
        print_info "Optimizaciones ya configuradas"
    fi
}

# =============================================================================
# 6. INSTALAR DEPENDENCIAS PYTHON
# =============================================================================

install_python_deps() {
    print_header "INSTALANDO DEPENDENCIAS PYTHON"
    
    # Crear directorio del proyecto
    mkdir -p ~/cognito-stack
    cd ~/cognito-stack
    
    print_info "Instalando paquetes Python..."
    pip3 install --user psutil
    
    print_success "Dependencias instaladas"
    
    # Crear requirements.txt
    cat > requirements.txt << 'EOF'
psutil>=5.9.0
EOF
    
    print_info "requirements.txt creado"
}

# =============================================================================
# 7. CREAR ARCHIVOS DEL PROYECTO
# =============================================================================

create_project_files() {
    print_header "CONFIGURANDO PROYECTO COGNITO STACK"
    
    cd ~/cognito-stack
    
    print_info "Los archivos Python del sistema ya están listos:"
    print_info "  - cognito_agent.py (copia del artifact)"
    print_info "  - monitor.py (copia del artifact)"
    
    # Crear script de inicio rápido
    cat > run_example.sh << 'EOF'
#!/bin/bash
# Script de ejemplo rápido para Cognito Stack

echo "🚀 Ejecutando ejemplo de Cognito Stack..."
python3 cognito_agent.py
EOF
    
    chmod +x run_example.sh
    
    print_success "Proyecto configurado en ~/cognito-stack/"
    print_info "Archivos creados:"
    ls -lh ~/cognito-stack/
}

# =============================================================================
# 8. EJECUTAR DIAGNÓSTICO
# =============================================================================

run_diagnostics() {
    print_header "EJECUTANDO DIAGNÓSTICO DEL SISTEMA"
    
    cd ~/cognito-stack
    
    if [ -f "monitor.py" ]; then
        python3 monitor.py diagnostics
    else
        print_warning "monitor.py no encontrado. Copia el código del artifact."
    fi
}

# =============================================================================
# MENÚ PRINCIPAL
# =============================================================================

show_menu() {
    clear
    echo -e "${BLUE}"
    cat << 'EOF'
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   ██████╗ ██████╗  ██████╗ ███╗   ██╗██╗████████╗ ██████╗                   ║
║  ██╔════╝██╔═══██╗██╔════╝ ████╗  ██║██║╚══██╔══╝██╔═══██╗                  ║
║  ██║     ██║   ██║██║  ███╗██╔██╗ ██║██║   ██║   ██║   ██║                  ║
║  ██║     ██║   ██║██║   ██║██║╚██╗██║██║   ██║   ██║   ██║                  ║
║  ╚██████╗╚██████╔╝╚██████╔╝██║ ╚████║██║   ██║   ╚██████╔╝                  ║
║   ╚═════╝ ╚═════╝  ╚═════╝ ╚═╝  ╚═══╝╚═╝   ╚═╝    ╚═════╝                   ║
║                                                                              ║
║              Sistema Multi-Razonamiento para RTX 5070 12GB                  ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
EOF
    echo -e "${NC}"
    
    echo "MENÚ DE INSTALACIÓN:"
    echo ""
    echo "  1) Instalación completa (recomendado)"
    echo "  2) Solo verificar requisitos"
    echo "  3) Solo configurar contenedor Ollama"
    echo "  4) Solo instalar modelos"
    echo "  5) Solo configurar optimizaciones"
    echo "  6) Limpiar modelos pesados"
    echo "  7) Ejecutar diagnóstico"
    echo "  8) Salir"
    echo ""
    read -p "Selecciona una opción (1-8): " choice
    
    case $choice in
        1)
            check_requirements
            setup_ollama_container
            install_models
            configure_optimizations
            install_python_deps
            create_project_files
            run_diagnostics
            print_success "¡Instalación completa!"
            ;;
        2)
            check_requirements
            ;;
        3)
            setup_ollama_container
            ;;
        4)
            install_models
            ;;
        5)
            configure_optimizations
            ;;
        6)
            cleanup_heavy_models
            ;;
        7)
            run_diagnostics
            ;;
        8)
            print_info "Saliendo..."
            exit 0
            ;;
        *)
            print_error "Opción inválida"
            ;;
    esac
    
    echo ""
    read -p "Presiona Enter para volver al menú..."
    show_menu
}

# =============================================================================
# MAIN
# =============================================================================

main() {
    if [ "$1" = "--auto" ]; then
        # Instalación automática completa
        check_requirements
        setup_ollama_container
        install_models
        configure_optimizations
        install_python_deps
        create_project_files
        run_diagnostics
    else
        # Modo interactivo
        show_menu
    fi
}

main "$@"
