#!/bin/bash
# Cognito Stack - Script de Limpieza y Optimización
# Para RTX 5070 12GB

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

CONTAINER="ollama-gpu"

print_header() {
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
}

print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }
print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }

# Obtener tamaño de modelo en GB
get_model_size_gb() {
    local size_str="$1"
    if [[ $size_str == *"GB"* ]]; then
        echo "$size_str" | sed 's/GB//' | awk '{print $1}'
    elif [[ $size_str == *"MB"* ]]; then
        echo "$size_str" | sed 's/MB//' | awk '{print $1/1024}'
    else
        echo "0"
    fi
}

# Verificar VRAM actual
check_vram() {
    print_header "VERIFICANDO ESTADO DE VRAM"
    
    vram_info=$(nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader,nounits)
    vram_used=$(echo $vram_info | awk '{print $1}')
    vram_total=$(echo $vram_info | awk '{print $2}')
    vram_percent=$(echo "scale=1; ($vram_used / $vram_total) * 100" | bc)
    
    echo "  VRAM Usado: ${vram_used}MB / ${vram_total}MB (${vram_percent}%)"
    
    if (( $(echo "$vram_percent > 90" | bc -l) )); then
        print_error "VRAM CRÍTICA (>90%)"
        return 1
    elif (( $(echo "$vram_percent > 75" | bc -l) )); then
        print_warning "VRAM ALTA (>75%)"
        return 2
    else
        print_success "VRAM OK (<75%)"
        return 0
    fi
}

# Liberar VRAM inmediatamente
free_vram() {
    print_header "LIBERANDO VRAM"
    
    print_info "Deteniendo procesos de Ollama..."
    docker exec $CONTAINER pkill ollama 2>/dev/null || true
    
    sleep 3
    
    print_success "VRAM liberada"
    check_vram
}

# Listar modelos pesados
list_heavy_models() {
    print_header "MODELOS PESADOS DETECTADOS"
    
    echo "  Modelos que NO caben en RTX 5070 12GB:"
    echo ""
    
    docker exec $CONTAINER ollama list | tail -n +2 | while read -r line; do
        name=$(echo $line | awk '{print $1}')
        size=$(echo $line | awk '{print $3}')
        size_gb=$(get_model_size_gb "$size")
        
        if (( $(echo "$size_gb > 15" | bc -l) )); then
            echo -e "  ${RED}❌ $name${NC} (${size}) - IMPOSIBLE ejecutar eficientemente"
        elif (( $(echo "$size_gb > 12" | bc -l) )); then
            echo -e "  ${YELLOW}⚠️  $name${NC} (${size}) - Limita contexto severamente"
        fi
    done
}

# Eliminar modelos automáticamente
auto_cleanup() {
    print_header "LIMPIEZA AUTOMÁTICA DE MODELOS"
    
    # Modelos que definitivamente deberías eliminar (>18GB)
    declare -a critical_remove=(
        "llama3.3:70b"
        "qwen3-coder:30b"
        "deepseek-r1:32b"
    )
    
    # Modelos que podrías considerar eliminar (15-18GB)
    declare -a optional_remove=(
        "gemma3:27b"
        "gpt-oss:20b"
    )
    
    echo "ELIMINANDO MODELOS CRÍTICOS (imposibles con 12GB VRAM):"
    echo ""
    
    for model in "${critical_remove[@]}"; do
        if docker exec $CONTAINER ollama list | grep -q "$model"; then
            print_info "Eliminando $model..."
            docker exec $CONTAINER ollama rm "$model" 2>/dev/null && \
                print_success "$model eliminado" || \
                print_warning "$model no se pudo eliminar"
        else
            print_info "$model no está instalado (ok)"
        fi
    done
    
    echo ""
    echo "MODELOS OPCIONALES A CONSIDERAR:"
    echo ""
    
    for model in "${optional_remove[@]}"; do
        if docker exec $CONTAINER ollama list | grep -q "$model"; then
            echo -e "  ${YELLOW}⚠️  $model${NC} - Puedes eliminarlo con: docker exec $CONTAINER ollama rm $model"
        fi
    done
}

# Mostrar modelos recomendados
show_recommended() {
    print_header "MODELOS RECOMENDADOS PARA RTX 5070 12GB"
    
    cat << 'EOF'
  ✅ TIER 1 - ESENCIALES (Routing & Meta)
     • deepseek-r1:7b (4.7GB)    - Routing ultrarrápido
     • cogito:8b (4.9GB)         - Metareasoning con deep thinking

  ✅ TIER 2 - RAZONAMIENTO (14B)
     • deepseek-r1:14b (9GB)     - Deducción potente
     • cogito:14b (9GB)          - Abducción con deep thinking
     • phi4:14b (9.1GB)          - Analogías avanzadas

  ✅ TIER 3 - ESPECIALIZADOS (14B)
     • qwen2.5-coder:14b (9GB)   - Código y acciones
     • qwen2.5:14b (9GB)         - Razonamiento general
     • gemma3:12b (8.1GB)        - Social/Conversación

  ✅ TIER 4 - LIGEROS (7-8B)
     • llama3.1:8b (4.9GB)       - Generación creativa
     • qwen3-vl:8b (6.1GB)       - Vision + Language
     • qwen3:8b (5.2GB)          - Multilingüe
     • qwen2.5:7b (4.7GB)        - General ligero
     • mistral:latest (4.4GB)    - Creativo

  RENDIMIENTO ESPERADO:
    • Modelos 7-8B: 40-45 t/s, contexto hasta 64K
    • Modelos 14B:  25-30 t/s, contexto hasta 16K
    • Puedes cargar 1x14B o 2x7B simultáneamente

EOF
}

# Verificar estado del sistema
system_status() {
    print_header "ESTADO DEL SISTEMA"
    
    # GPU
    echo "  🖥️  GPU:"
    nvidia-smi --query-gpu=name,temperature.gpu,power.draw --format=csv,noheader
    
    # VRAM
    echo ""
    check_vram
    
    # Contenedor
    echo ""
    echo "  🐳 Contenedor:"
    if docker ps | grep -q $CONTAINER; then
        print_success "Contenedor $CONTAINER está corriendo"
    else
        print_error "Contenedor $CONTAINER NO está corriendo"
    fi
    
    # Modelos cargados
    echo ""
    echo "  📦 Modelos en memoria:"
    loaded=$(docker exec $CONTAINER ollama ps 2>/dev/null | tail -n +2 | wc -l)
    echo "     $loaded modelos cargados"
    
    if [ $loaded -gt 2 ]; then
        print_warning "Tienes $loaded modelos cargados. Con 12GB VRAM, óptimo es 1-2."
    fi
    
    # Total de modelos
    echo ""
    echo "  📊 Modelos disponibles:"
    docker exec $CONTAINER ollama list | tail -n +2 | wc -l | xargs -I {} echo "     {} modelos instalados"
}

# Modo interactivo
interactive_mode() {
    while true; do
        clear
        cat << 'EOF'
╔══════════════════════════════════════════════════════════════════════════════╗
║              COGNITO STACK - HERRAMIENTA DE LIMPIEZA                         ║
║                    Optimizado para RTX 5070 12GB                             ║
╚══════════════════════════════════════════════════════════════════════════════╝

EOF
        
        echo "  1) Ver estado del sistema"
        echo "  2) Liberar VRAM inmediatamente"
        echo "  3) Listar modelos pesados"
        echo "  4) Limpieza automática (elimina modelos >18GB)"
        echo "  5) Ver modelos recomendados"
        echo "  6) Ejecutar diagnóstico completo (monitor.py)"
        echo "  7) Salir"
        echo ""
        read -p "  Selecciona una opción (1-7): " choice
        
        case $choice in
            1)
                system_status
                ;;
            2)
                free_vram
                ;;
            3)
                list_heavy_models
                ;;
            4)
                echo ""
                read -p "  ¿Estás seguro de eliminar modelos pesados? (y/n): " confirm
                if [ "$confirm" = "y" ]; then
                    auto_cleanup
                else
                    print_info "Operación cancelada"
                fi
                ;;
            5)
                show_recommended
                ;;
            6)
                if [ -f "monitor.py" ]; then
                    python3 monitor.py diagnostics
                else
                    print_error "monitor.py no encontrado"
                fi
                ;;
            7)
                print_info "Saliendo..."
                exit 0
                ;;
            *)
                print_error "Opción inválida"
                ;;
        esac
        
        echo ""
        read -p "  Presiona Enter para continuar..."
    done
}

# Main
main() {
    if [ "$1" = "--auto" ]; then
        system_status
        check_vram
        vram_status=$?
        
        if [ $vram_status -eq 1 ] || [ $vram_status -eq 2 ]; then
            free_vram
            list_heavy_models
            
            echo ""
            read -p "¿Ejecutar limpieza automática? (y/n): " confirm
            if [ "$confirm" = "y" ]; then
                auto_cleanup
            fi
        fi
        
        show_recommended
        
    elif [ "$1" = "--free" ]; then
        free_vram
        
    elif [ "$1" = "--clean" ]; then
        auto_cleanup
        
    elif [ "$1" = "--status" ]; then
        system_status
        
    else
        interactive_mode
    fi
}

main "$@"
