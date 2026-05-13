#!/bin/bash
# Script de testing simplificado

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

RESULTS_FILE="test_results_$(date +%Y%m%d_%H%M%S).log"
PASSED=0
FAILED=0

log_section() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

test_pass() {
    echo -e "${GREEN}✓ PASS:${NC} $1"
    ((PASSED++))
}

test_fail() {
    echo -e "${RED}✗ FAIL:${NC} $1"
    ((FAILED++))
}

test_warn() {
    echo -e "${YELLOW}⚠ WARN:${NC} $1"
}

# FASE 1: INFRAESTRUCTURA
log_section "FASE 1: INFRAESTRUCTURA BASE"

echo "1.1 - Docker containers..."
docker ps --format "table {{.Names}}\t{{.Status}}" | head -20

echo -e "\n1.2 - PostgreSQL..."
if docker exec postgres pg_isready -U postgres > /dev/null 2>&1; then
    test_pass "PostgreSQL responde"
else
    test_fail "PostgreSQL no responde"
fi

echo -e "\n1.3 - Redis..."
if docker exec redis redis-cli ping 2>/dev/null | grep -q "PONG"; then
    test_pass "Redis responde"
else
    test_fail "Redis no responde"
fi

echo -e "\n1.4 - Qdrant..."
if curl -sf http://localhost:6333 > /dev/null; then
    test_pass "Qdrant responde"
else
    test_fail "Qdrant no responde"
fi

# FASE 2: SERVICIOS DE IA
log_section "FASE 2: SERVICIOS DE IA"

echo "2.1 - Ollama..."
if curl -sf http://localhost:11434/api/tags > /dev/null; then
    MODELS=$(curl -s http://localhost:11434/api/tags | jq -r '.models[].name' | wc -l)
    test_pass "Ollama responde con $MODELS modelos"
else
    test_fail "Ollama no responde"
fi

echo -e "\n2.2 - Whisper STT..."
if curl -sf http://localhost:9001/health > /dev/null; then
    test_pass "Whisper STT responde"
else
    test_fail "Whisper STT no responde"
fi

echo -e "\n2.3 - Kokoro TTS..."
if docker exec kokoro-tts curl -sf http://localhost:8880/health > /dev/null 2>&1; then
    test_pass "Kokoro TTS responde (interno)"
else
    test_fail "Kokoro TTS no responde"
fi

echo -e "\n2.4 - ComfyUI..."
if curl -sf http://localhost:8188/ > /dev/null; then
    test_pass "ComfyUI responde"
else
    test_fail "ComfyUI no responde"
fi

# FASE 3: SERVICIOS WEB
log_section "FASE 3: SERVICIOS WEB"

echo "3.1 - n8n..."
if curl -sf http://localhost:5678/healthz > /dev/null; then
    test_pass "n8n responde"
else
    test_fail "n8n no responde"
fi

echo -e "\n3.2 - Forgejo..."
if curl -sf http://localhost:3002/ > /dev/null; then
    test_pass "Forgejo responde"
else
    test_fail "Forgejo no responde"
fi

echo -e "\n3.3 - nginx-proxy..."
if curl -sf http://localhost:80 > /dev/null; then
    test_pass "nginx-proxy responde"
else
    test_fail "nginx-proxy no responde"
fi

# RESUMEN
log_section "RESUMEN"
echo -e "${GREEN}Pasados: $PASSED${NC}"
echo -e "${RED}Fallidos: $FAILED${NC}"

if [ $FAILED -eq 0 ]; then
    echo -e "\n${GREEN}🎉 Todos los tests pasaron!${NC}"
else
    echo -e "\n${YELLOW}Revisar servicios con problemas${NC}"
fi
