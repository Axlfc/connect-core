#!/bin/bash
set -e

echo "=========================================="
echo "Comprehensive Docker Compose Fix Script"
echo "=========================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Stop all services
echo ""
echo -e "${YELLOW}Stopping all services...${NC}"
docker compose down

# Fix secret permissions
echo ""
echo -e "${YELLOW}Fixing secret file permissions...${NC}"
if [ -d "./secrets" ]; then
    chmod 644 ./secrets/*.txt 2>/dev/null || true
    echo -e "${GREEN}✓ Secret files are readable${NC}"
else
    echo -e "${RED}✗ No secrets directory found${NC}"
fi

# Remove problematic log mounts from docker-compose.yml
echo ""
echo -e "${YELLOW}Removing problematic log volume mounts...${NC}"

# Backup original
cp docker-compose.yml docker-compose.yml.backup

# Remove log mounts that cause permission issues
sed -i '/- \.\/logs\/ollama:\/var\/log\/ollama/d' docker-compose.yml
sed -i '/- \.\/logs\/whisper-stt:\/var\/log\/whisper-stt/d' docker-compose.yml
sed -i '/- \.\/logs\/whisper-stt-cpu:\/var\/log\/whisper-stt-cpu/d' docker-compose.yml
sed -i '/- \.\/logs\/kokoro-tts:\/var\/log\/kokoro-tts/d' docker-compose.yml
sed -i '/- \.\/logs\/kokoro-tts-cpu:\/var\/log\/kokoro-tts-cpu/d' docker-compose.yml
sed -i '/- \.\/logs\/voice-gateway:\/var\/log\/voice-gateway/d' docker-compose.yml
sed -i '/- \.\/logs\/qdrant:\/var\/log\/qdrant/d' docker-compose.yml
sed -i '/- \.\/logs\/n8n-runner:\/var\/log\/n8n-runner/d' docker-compose.yml

# Change commands to not redirect to log files
sed -i 's|command: /bin/sh -c "exec ollama serve >> /var/log/ollama/output.log 2>&1"|command: serve|g' docker-compose.yml
sed -i 's|command: /bin/sh -c "exec whisper-asr-webservice --host 0.0.0.0 --port 9000 --model large-v3 >> /var/log/whisper-stt/output.log 2>&1"|command: ["whisper-asr-webservice", "--host", "0.0.0.0", "--port", "9000", "--model", "large-v3"]|g' docker-compose.yml
sed -i 's|command: /bin/sh -c "exec whisper-asr-webservice --host 0.0.0.0 --port 9000 --model base.en >> /var/log/whisper-stt-cpu/output.log 2>&1"|command: ["whisper-asr-webservice", "--host", "0.0.0.0", "--port", "9000", "--model", "base.en"]|g' docker-compose.yml
sed -i 's|command: /bin/sh -c "exec uvicorn main:app --host 0.0.0.0 --port 8880 >> /var/log/kokoro-tts/output.log 2>&1"|command: ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8880"]|g' docker-compose.yml
sed -i 's|command: /bin/sh -c "exec uvicorn main:app --host 0.0.0.0 --port 9000 >> /var/log/voice-gateway/output.log 2>&1"|command: ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9000"]|g' docker-compose.yml
sed -i 's|command: /bin/sh -c "exec ./qdrant --log-level info >> /var/log/qdrant/output.log 2>&1"|command: ["./qdrant", "--log-level", "info"]|g' docker-compose.yml
sed -i 's|command: /bin/sh -c "exec n8n start --runner >> /var/log/n8n-runner/output.log 2>&1"|command: ["n8n", "start", "--runner"]|g' docker-compose.yml

# Remove version line
sed -i '/^version:/d' docker-compose.yml

echo -e "${GREEN}✓ docker-compose.yml updated${NC}"
echo "  Backup saved as docker-compose.yml.backup"

# Check GPU availability
echo ""
echo -e "${YELLOW}Checking NVIDIA GPU support...${NC}"
if command -v nvidia-smi &> /dev/null; then
    echo -e "${GREEN}✓ nvidia-smi found${NC}"
    GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo "Unknown")
    echo "  GPU: $GPU_NAME"
    
    # Check Docker GPU support
    if docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi &> /dev/null 2>&1; then
        echo -e "${GREEN}✓ Docker can access NVIDIA GPU${NC}"
        GPU_OK=true
    else
        echo -e "${RED}✗ Docker cannot access GPU${NC}"
        echo "  Install nvidia-container-toolkit and restart Docker"
        GPU_OK=false
    fi
else
    echo -e "${RED}✗ nvidia-smi not found${NC}"
    echo "  NVIDIA drivers may not be installed"
    GPU_OK=false
fi

# Start services based on GPU availability
echo ""
if [ "$GPU_OK" = true ]; then
    echo -e "${GREEN}Starting services with GPU support...${NC}"
    PROFILES="--profile gpu-nvidia --profile voice"
else
    echo -e "${YELLOW}Starting services with CPU-only mode...${NC}"
    PROFILES="--profile cpu --profile voice-cpu"
fi

echo ""
echo "Starting core infrastructure first..."
docker compose up -d postgres redis qdrant

echo ""
echo "Waiting 15 seconds for databases..."
sleep 15

echo ""
echo "Checking database health..."
docker compose ps postgres redis qdrant

echo ""
echo "Starting AI services..."
docker compose $PROFILES up -d

echo ""
echo "Waiting for services to stabilize..."
sleep 10

echo ""
echo "=========================================="
echo "Service Status"
echo "=========================================="
docker compose ps

echo ""
echo "=========================================="
echo "Health Check Summary"
echo "=========================================="

# Check each critical service
check_service() {
    local service=$1
    if docker compose ps --format json | jq -r ".[] | select(.Service==\"$service\") | .Health" | grep -q "healthy"; then
        echo -e "${GREEN}✓${NC} $service: healthy"
    elif docker compose ps --format json | jq -r ".[] | select(.Service==\"$service\") | .State" | grep -q "running"; then
        echo -e "${YELLOW}⚠${NC} $service: running (no healthcheck or starting)"
    else
        echo -e "${RED}✗${NC} $service: unhealthy or not running"
    fi
}

check_service "postgres"
check_service "redis"
check_service "qdrant"
check_service "ollama-gpu" || check_service "ollama-cpu"
check_service "whisper-stt" || check_service "whisper-stt-cpu"
check_service "kokoro-tts" || check_service "kokoro-tts-cpu"
check_service "n8n"

echo ""
echo "=========================================="
echo "Next Steps"
echo "=========================================="
echo "1. Check logs of any failing services:"
echo "   docker compose logs <service-name>"
echo ""
echo "2. View real-time logs:"
echo "   docker compose logs -f"
echo ""
echo "3. Access services:"
if [ "$GPU_OK" = true ]; then
    echo "   - Ollama: http://localhost:11434"
fi
echo "   - n8n: http://localhost:5678"
echo "   - Qdrant: http://localhost:6333"
echo ""
echo "4. If services are still failing, check:"
echo "   docker compose logs ollama-gpu"
echo "   docker compose logs whisper-stt"
echo "   docker compose logs kokoro-tts"
