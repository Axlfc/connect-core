#!/bin/bash

# Script interactivo para inicializar .env desde .env.example

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
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

print_header() {
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║  $1${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════╝${NC}"
    echo ""
}

# Función para generar valores aleatorios seguros
generate_secure_value() {
    local length=${1:-64}
    if command -v openssl &> /dev/null; then
        openssl rand -hex $((length / 2))
    elif command -v python3 &> /dev/null; then
        python3 -c "import secrets; print(secrets.token_hex($((length / 2))))"
    else
        cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w "$length" | head -n 1
    fi
}

# Configuración
SOURCE_FILE=".env.example"
TARGET_FILE=".env"
BACKUP_FILE=".env.backup.$(date +%Y%m%d_%H%M%S)"
INTERACTIVE=true

# Parsear argumentos
while [[ $# -gt 0 ]]; do
    case $1 in
        --auto|-a)
            INTERACTIVE=false
            shift
            ;;
        --help|-h)
            echo "Uso: $0 [OPTIONS]"
            echo ""
            echo "Opciones:"
            echo "  -a, --auto    Modo automático (genera valores sin preguntar)"
            echo "  -h, --help    Muestra esta ayuda"
            echo ""
            echo "Modo por defecto: interactivo"
            exit 0
            ;;
        *)
            print_error "Opción desconocida: $1"
            exit 1
            ;;
    esac
done

print_header "Inicializador de Entorno - AI Stack"

# Verificar que existe .env.example
if [[ ! -f "$SOURCE_FILE" ]]; then
    print_error "No se encontró $SOURCE_FILE"
    echo "Ejecuta primero: ./generate_env_example.sh"
    exit 1
fi

# Si existe .env, hacer backup
if [[ -f "$TARGET_FILE" ]]; then
    if [[ "$INTERACTIVE" == true ]]; then
        echo -e "${YELLOW}⚠️  Ya existe un archivo .env${NC}"
        echo -n "¿Quieres hacer un backup y continuar? (s/N): "
        read -r response
        if [[ ! "$response" =~ ^[sS]$ ]]; then
            print_info "Operación cancelada"
            exit 0
        fi
    fi
    
    cp "$TARGET_FILE" "$BACKUP_FILE"
    print_success "Backup creado: $BACKUP_FILE"
fi

# Copiar .env.example a .env
cp "$SOURCE_FILE" "$TARGET_FILE"
print_info "Archivo .env creado desde .env.example"

echo ""
print_header "Generación de Valores Seguros"

# Variables que necesitan valores generados
SECURE_VARS=(
    "N8N_ENCRYPTION_KEY"
    "N8N_USER_MANAGEMENT_JWT_SECRET"
    "N8N_AUTH_JWT_SECRET"
    "N8N_RUNNERS_AUTH_TOKEN"
    "POSTGRES_PASSWORD"
    "REDIS_PASSWORD"
    "FORGEJO_DB_PASSWORD"
)

# Generar valores seguros
for var in "${SECURE_VARS[@]}"; do
    # Verificar si la variable existe y está vacía
    if grep -q "^${var}=$" "$TARGET_FILE"; then
        new_value=$(generate_secure_value 64)
        
        if [[ "$INTERACTIVE" == true ]]; then
            echo ""
            echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
            echo -e "${BLUE}Variable:${NC} $var"
            echo -e "${BLUE}Valor generado:${NC} ${new_value:0:20}...${new_value: -10}"
            echo -n "¿Usar este valor? (S/n/personalizar): "
            read -r response
            
            case "$response" in
                [nN])
                    print_info "Saltando $var (deberás rellenarlo manualmente)"
                    continue
                    ;;
                [pP]*)
                    echo -n "Introduce el valor para $var: "
                    read -r new_value
                    ;;
                *)
                    # Por defecto, usar el generado (S o Enter)
                    ;;
            esac
        fi
        
        # Actualizar el archivo
        sed -i "s|^${var}=.*|${var}=${new_value}|" "$TARGET_FILE"
        print_success "$var configurado"
    fi
done

echo ""
print_header "Configuración de Servicios Opcionales"

# Variables opcionales que el usuario debe decidir
OPTIONAL_VARS=(
    "TELEGRAM_BOT_TOKEN:Token del bot de Telegram (@BotFather)"
    "ZROK_AUTH_TOKEN:Token de Zrok (https://zrok.io)"
    "MCP_BRAVE_API_KEY:API Key de Brave Search"
)

for var_info in "${OPTIONAL_VARS[@]}"; do
    IFS=':' read -r var desc <<< "$var_info"
    
    if grep -q "^${var}=$" "$TARGET_FILE"; then
        if [[ "$INTERACTIVE" == true ]]; then
            echo ""
            echo -e "${BLUE}$desc${NC}"
            echo -n "¿Quieres configurar $var ahora? (s/N): "
            read -r response
            
            if [[ "$response" =~ ^[sS]$ ]]; then
                echo -n "Introduce el valor: "
                read -r value
                sed -i "s|^${var}=.*|${var}=${value}|" "$TARGET_FILE"
                print_success "$var configurado"
            else
                print_info "$var se puede configurar después"
            fi
        fi
    fi
done

echo ""
print_header "Resumen de Configuración"

# Contar variables configuradas vs vacías
total_vars=$(grep -c '^[[:alnum:]_]*=' "$TARGET_FILE" 2>/dev/null || echo 0)
empty_vars=$(grep -c '^[[:alnum:]_]*=$' "$TARGET_FILE" 2>/dev/null || echo 0)
filled_vars=$((total_vars - empty_vars))

echo -e "${BLUE}📊 Estadísticas:${NC}"
echo "   Total de variables: $total_vars"
echo "   Configuradas: $filled_vars"
echo "   Por configurar: $empty_vars"
echo ""

if [[ $empty_vars -gt 0 ]]; then
    print_warning "Hay $empty_vars variables sin configurar"
    echo ""
    echo "Variables vacías:"
    grep '^[[:alnum:]_]*=$' "$TARGET_FILE" | cut -d'=' -f1 | while read -r var; do
        echo "   • $var"
    done
    echo ""
    print_info "Puedes editarlas en: $TARGET_FILE"
fi

echo ""
print_header "✅ Configuración Completada"

echo "Archivo generado: $TARGET_FILE"
if [[ -f "$BACKUP_FILE" ]]; then
    echo "Backup anterior: $BACKUP_FILE"
fi
echo ""

echo -e "${CYAN}🚀 Próximos pasos:${NC}"
echo ""
echo "1. Revisa las variables en .env:"
echo "   ${YELLOW}nano .env${NC}  o  ${YELLOW}vim .env${NC}"
echo ""
echo "2. Rellena las variables opcionales que necesites"
echo ""
echo "3. Inicia los servicios:"
echo "   ${GREEN}./start.sh${NC}                    # GPU NVIDIA"
echo "   ${GREEN}./start.sh --voice${NC}            # Con servicios de voz"
echo "   ${GREEN}./start.sh --cpu --voice${NC}      # CPU con voz"
echo ""
echo "4. Verifica que todo funciona:"
echo "   ${GREEN}docker compose ps${NC}"
echo ""

if [[ $empty_vars -gt 0 ]]; then
    print_warning "IMPORTANTE: Algunas variables están vacías"
    echo "Los servicios pueden no funcionar correctamente hasta que las configures"
fi

echo ""
