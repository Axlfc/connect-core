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

print_header "DIAGNÓSTICO DE SERVICIOS DE VOZ"

# Detectar qué contenedores existen
WHISPER=""
KOKORO=""
GATEWAY=""

if docker ps -a --format '{{.Names}}' | grep -q "^whisper-stt$"; then
    WHISPER="whisper-stt"
elif docker ps -a --format '{{.Names}}' | grep -q "^whisper-stt-cpu$"; then
    WHISPER="whisper-stt-cpu"
fi

if docker ps -a --format '{{.Names}}' | grep -q "^kokoro-tts$"; then
    KOKORO="kokoro-tts"
elif docker ps -a --format '{{.Names}}' | grep -q "^kokoro-tts-cpu$"; then
    KOKORO="kokoro-tts-cpu"
fi

if docker ps -a --format '{{.Names}}' | grep -q "^voice-gateway$"; then
    GATEWAY="voice-gateway"
fi

# ========================================
# WHISPER
# ========================================
if [ -n "$WHISPER" ]; then
    print_header "WHISPER STT ($WHISPER)"
    
    # Estado del contenedor
    STATUS=$(docker inspect --format='{{.State.Status}}' "$WHISPER" 2>/dev/null)
    HEALTH=$(docker inspect --format='{{.State.Health.Status}}' "$WHISPER" 2>/dev/null)
    
    echo "Estado: $STATUS"
    echo "Health: $HEALTH"
    echo ""
    
    # Logs recientes
    print_info "Últimos 30 logs:"
    docker logs --tail 30 "$WHISPER" 2>&1
    
    echo ""
    
    # Probar API si está corriendo
    if [ "$STATUS" = "running" ]; then
        print_info "Probando API en puerto 9001..."
        RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:9001/ 2>/dev/null || echo "FAIL")
        
        if [ "$RESPONSE" = "200" ]; then
            print_success "API responde correctamente (HTTP $RESPONSE)"
        else
            print_warning "API no responde (HTTP $RESPONSE)"
        fi
    fi
else
    print_warning "Whisper no encontrado"
fi

# ========================================
# KOKORO
# ========================================
if [ -n "$KOKORO" ]; then
    echo ""
    print_header "KOKORO TTS ($KOKORO)"
    
    # Estado
    STATUS=$(docker inspect --format='{{.State.Status}}' "$KOKORO" 2>/dev/null)
    HEALTH=$(docker inspect --format='{{.State.Health.Status}}' "$KOKORO" 2>/dev/null)
    
    echo "Estado: $STATUS"
    echo "Health: $HEALTH"
    echo ""
    
    # Logs
    print_info "Últimos 50 logs:"
    docker logs --tail 50 "$KOKORO" 2>&1
    
    echo ""
    
    # Probar API
    if [ "$STATUS" = "running" ]; then
        print_info "Probando API en puerto 8880..."
        
        # Probar endpoint /health
        RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8880/health 2>/dev/null || echo "FAIL")
        
        if [ "$RESPONSE" = "200" ]; then
            print_success "API /health responde (HTTP $RESPONSE)"
        else
            print_warning "API /health no responde (HTTP $RESPONSE)"
        fi
        
        # Probar endpoint raíz
        RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8880/ 2>/dev/null || echo "FAIL")
        
        if [ "$RESPONSE" = "200" ]; then
            print_success "API / responde (HTTP $RESPONSE)"
        else
            print_info "API / responde con HTTP $RESPONSE (puede ser normal)"
        fi
    fi
else
    print_warning "Kokoro no encontrado"
fi

# ========================================
# VOICE GATEWAY
# ========================================
if [ -n "$GATEWAY" ]; then
    echo ""
    print_header "VOICE GATEWAY"
    
    # Estado
    STATUS=$(docker inspect --format='{{.State.Status}}' "$GATEWAY" 2>/dev/null)
    HEALTH=$(docker inspect --format='{{.State.Health.Status}}' "$GATEWAY" 2>/dev/null)
    
    echo "Estado: $STATUS"
    echo "Health: $HEALTH"
    echo ""
    
    # Logs
    print_info "Últimos 30 logs:"
    docker logs --tail 30 "$GATEWAY" 2>&1
    
    echo ""
    
    # Probar API
    if [ "$STATUS" = "running" ]; then
        print_info "Probando API en puerto 9002..."
        RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:9002/health 2>/dev/null || echo "FAIL")
        
        if [ "$RESPONSE" = "200" ]; then
            print_success "Voice Gateway responde (HTTP $RESPONSE)"
        else
            print_warning "Voice Gateway no responde (HTTP $RESPONSE)"
        fi
    fi
else
    print_warning "Voice Gateway no encontrado"
fi

# ========================================
# RESUMEN Y RECOMENDACIONES
# ========================================
echo ""
print_header "RESUMEN Y RECOMENDACIONES"

# Whisper
if [ -n "$WHISPER" ]; then
    WHISPER_STATUS=$(docker inspect --format='{{.State.Status}}' "$WHISPER" 2>/dev/null)
    WHISPER_HEALTH=$(docker inspect --format='{{.State.Health.Status}}' "$WHISPER" 2>/dev/null)
    
    if [ "$WHISPER_STATUS" != "running" ] || [ "$WHISPER_HEALTH" = "unhealthy" ]; then
        print_error "Whisper tiene problemas"
        echo "  • Ver logs completos: docker logs -f $WHISPER"
        echo "  • Reiniciar: docker restart $WHISPER"
        echo "  • Verificar puerto 9001: netstat -tlnp | grep 9001"
    else
        print_success "Whisper operativo"
    fi
fi

# Kokoro
if [ -n "$KOKORO" ]; then
    KOKORO_STATUS=$(docker inspect --format='{{.State.Status}}' "$KOKORO" 2>/dev/null)
    KOKORO_HEALTH=$(docker inspect --format='{{.State.Health.Status}}' "$KOKORO" 2>/dev/null)
    
    if [ "$KOKORO_STATUS" != "running" ] || [ "$KOKORO_HEALTH" = "unhealthy" ]; then
        print_error "Kokoro tiene problemas"
        echo "  • Ver logs completos: docker logs -f $KOKORO"
        echo "  • Reiniciar: docker restart $KOKORO"
        echo "  • El modelo puede tardar 60-90s en cargar"
    else
        print_success "Kokoro operativo"
    fi
fi

# Gateway
if [ -n "$GATEWAY" ]; then
    GATEWAY_STATUS=$(docker inspect --format='{{.State.Status}}' "$GATEWAY" 2>/dev/null)
    GATEWAY_HEALTH=$(docker inspect --format='{{.State.Health.Status}}' "$GATEWAY" 2>/dev/null)
    
    if [ "$GATEWAY_STATUS" != "running" ] || [ "$GATEWAY_HEALTH" = "unhealthy" ]; then
        print_error "Voice Gateway tiene problemas"
        echo "  • Ver logs: docker logs -f $GATEWAY"
        echo "  • Verificar que Whisper y Kokoro estén operativos primero"
    else
        print_success "Voice Gateway operativo"
    fi
fi

echo ""
print_info "💡 Comandos útiles:"
echo "  docker logs -f [servicio]         # Ver logs en tiempo real"
echo "  docker restart [servicio]         # Reiniciar servicio"
echo "  docker exec -it [servicio] bash   # Entrar al contenedor"
echo ""
