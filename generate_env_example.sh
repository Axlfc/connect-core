#!/bin/bash

# Script inteligente para generar .env.example desde .env
# Preserva valores de ejemplo útiles y respeta configuración existente

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

# Configuración
INPUT_FILE="${1:-.env}"
OUTPUT_FILE="${2:-.env.example}"
BACKUP_FILE="${OUTPUT_FILE}.backup"

# Valores de ejemplo que queremos mantener (no vaciar)
# Estos son valores útiles para la documentación
declare -A EXAMPLE_VALUES=(
    ["WHISPER_MODEL"]="base.en"
    ["KOKORO_MODEL_NAME"]="kokoro-v0_19"
    ["KOKORO_COMPUTE_TYPE"]="float16"
    ["VOICE_GATEWAY_PORT"]="9000"
    ["POSTGRES_PORT"]="5432"
    ["REDIS_VERSION"]="7.2"
    ["REDIS_PORT"]="6379"
    ["REDIS_MAXMEMORY"]="256mb"
    ["REDIS_MAXMEMORY_POLICY"]="allkeys-lru"
    ["REDIS_TCP_BACKLOG"]="511"
    ["POSTGRES_USER_ID"]="999"
    ["POSTGRES_GROUP_ID"]="999"
    ["REDIS_USER_ID"]="999"
    ["REDIS_GROUP_ID"]="999"
    ["ZROK_API_ENDPOINT"]="https://api.zrok.io"
    ["ZROK_SHARE_MODE"]="public"
    ["WEBHOOK_URL"]="http://localhost:5678"
    ["N8N_DB_SCHEMA"]="public"
)

# Patrones que indican valores sensibles a vaciar
SENSITIVE_PATTERNS=(
    "PASSWORD"
    "SECRET"
    "KEY"
    "TOKEN"
    "AUTH"
    "JWT"
)

# Función para verificar si una variable es sensible
is_sensitive() {
    local var_name="$1"
    for pattern in "${SENSITIVE_PATTERNS[@]}"; do
        if [[ "$var_name" == *"$pattern"* ]]; then
            return 0  # Es sensible
        fi
    done
    return 1  # No es sensible
}

# Función para obtener el valor de ejemplo apropiado
get_example_value() {
    local var_name="$1"
    local current_value="$2"
    local existing_example="$3"
    
    # Si hay un valor predefinido, usarlo
    if [[ -n "${EXAMPLE_VALUES[$var_name]}" ]]; then
        echo "${EXAMPLE_VALUES[$var_name]}"
        return
    fi
    
    # Si es sensible, vaciar
    if is_sensitive "$var_name"; then
        echo ""
        return
    fi
    
    # Si existe un .env.example con valor, preservarlo
    if [[ -n "$existing_example" ]] && [[ "$existing_example" != "" ]]; then
        echo "$existing_example"
        return
    fi
    
    # Si el valor actual parece ser ejemplo/documentación (no real), preservarlo
    # Detectamos patrones como: "your_*_here", "change_this", "example", etc.
    if [[ "$current_value" =~ ^(your_|example|test|demo|change_this) ]] || \
       [[ "$current_value" =~ (here|change|this)$ ]]; then
        echo "$current_value"
        return
    fi
    
    # Si el valor no parece sensible y es corto (posiblemente configuración), preservarlo
    if [[ ${#current_value} -lt 50 ]]; then
        echo "$current_value"
        return
    fi
    
    # Por defecto, vaciar
    echo ""
}

# Función para cargar valores existentes de .env.example
load_existing_examples() {
    local file="$1"
    declare -gA EXISTING_EXAMPLES
    
    if [[ ! -f "$file" ]]; then
        return
    fi
    
    while IFS='=' read -r key value; do
        # Ignorar comentarios y líneas vacías
        if [[ "$key" =~ ^[[:space:]]*# ]] || [[ -z "$key" ]]; then
            continue
        fi
        # Limpiar espacios
        key=$(echo "$key" | xargs)
        value=$(echo "$value" | xargs)
        EXISTING_EXAMPLES["$key"]="$value"
    done < "$file"
}

echo -e "${BLUE}╔═══════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Generador Inteligente de .env.example       ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════╝${NC}"
echo ""

# Validaciones
if [[ ! -f "$INPUT_FILE" ]]; then
    print_error "El archivo '$INPUT_FILE' no existe."
    echo "Uso: $0 [archivo_entrada.env] [archivo_salida.env.example]"
    exit 1
fi

# Cargar valores existentes del .env.example si existe
if [[ -f "$OUTPUT_FILE" ]]; then
    print_info "Cargando valores existentes de $OUTPUT_FILE"
    load_existing_examples "$OUTPUT_FILE"
    
    # Hacer backup
    cp "$OUTPUT_FILE" "$BACKUP_FILE"
    print_info "Backup creado: $BACKUP_FILE"
fi

# Procesar el archivo
print_info "Procesando $INPUT_FILE..."
echo ""

{
    while IFS= read -r line; do
        # Preservar líneas vacías y comentarios tal cual
        if [[ "$line" =~ ^[[:space:]]*$ ]] || [[ "$line" =~ ^[[:space:]]*# ]]; then
            echo "$line"
            continue
        fi
        
        # Extraer variable y valor
        if [[ "$line" =~ ^([[:alnum:]_]+)=(.*)$ ]]; then
            var_name="${BASH_REMATCH[1]}"
            current_value="${BASH_REMATCH[2]}"
            
            # Obtener valor existente del .env.example
            existing_example="${EXISTING_EXAMPLES[$var_name]}"
            
            # Determinar el valor de ejemplo apropiado
            example_value=$(get_example_value "$var_name" "$current_value" "$existing_example")
            
            # Mostrar información
            if is_sensitive "$var_name"; then
                echo -e "   ${YELLOW}🔒 $var_name${NC} (sensible - vaciado)" >&2
            elif [[ -n "$example_value" ]]; then
                if [[ "$example_value" == "$existing_example" ]]; then
                    echo -e "   ${BLUE}♻️  $var_name${NC} (preservado de .env.example)" >&2
                elif [[ -n "${EXAMPLE_VALUES[$var_name]}" ]]; then
                    echo -e "   ${GREEN}📝 $var_name${NC} (valor predefinido)" >&2
                else
                    echo -e "   ${GREEN}✓ $var_name${NC} (preservado)" >&2
                fi
            else
                echo -e "   ${YELLOW}∅ $var_name${NC} (vaciado)" >&2
            fi
            
            # Escribir la línea
            echo "${var_name}=${example_value}"
        else
            # Preservar líneas que no son variables
            echo "$line"
        fi
    done
} < "$INPUT_FILE" > "$OUTPUT_FILE"

echo ""
print_success "Archivo generado: $OUTPUT_FILE"

# Estadísticas
total_vars=$(grep -c '^[[:alnum:]_]*=' "$OUTPUT_FILE" 2>/dev/null || echo 0)
empty_vars=$(grep -c '^[[:alnum:]_]*=$' "$OUTPUT_FILE" 2>/dev/null || echo 0)
filled_vars=$((total_vars - empty_vars))

echo ""
echo -e "${BLUE}📊 Estadísticas:${NC}"
echo "   Total de variables: $total_vars"
echo "   Con valores: $filled_vars"
echo "   Vacías (sensibles): $empty_vars"

if [[ -f "$BACKUP_FILE" ]]; then
    echo ""
    print_info "Se creó un backup del anterior: $BACKUP_FILE"
fi

echo ""
echo -e "${BLUE}💡 Próximos pasos:${NC}"
echo "   1. Revisa $OUTPUT_FILE"
echo "   2. Edita valores si es necesario"
echo "   3. Copia a .env para usar: cp $OUTPUT_FILE .env"
echo "   4. Rellena las variables vacías (sensibles)"
echo ""
