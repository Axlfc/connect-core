#!/bin/bash
echo "=== Voice Services Health Check ==="
echo ""

echo "1. Checking if services are running..."
docker compose ps --format "table {{.Service}}\t{{.Status}}" | grep -E "whisper|kokoro|voice-gateway|ollama"

echo ""
echo "2. Testing Whisper STT..."
curl -s http://localhost:9001/health && echo "✅ Whisper OK" || echo "❌ Whisper FAIL"

echo ""
echo "3. Testing Kokoro TTS..."
curl -s http://localhost:8880/health && echo "✅ Kokoro OK" || echo "❌ Kokoro FAIL"

echo ""
echo "4. Testing Ollama..."
curl -s http://localhost:11434/api/tags > /dev/null && echo "✅ Ollama OK" || echo "❌ Ollama FAIL"

echo ""
echo "5. Testing Voice Gateway..."
curl -s http://localhost:9002/health && echo "✅ Gateway OK" || echo "❌ Gateway FAIL"

echo ""
echo "6. Checking internal network connectivity..."
docker exec voice-gateway sh -c "apk add --no-cache curl 2>/dev/null; curl -s http://whisper-stt:9000/health" && echo "✅ Gateway → Whisper OK" || echo "❌ Gateway → Whisper FAIL"

docker exec voice-gateway sh -c "curl -s http://kokoro-tts:8880/health" && echo "✅ Gateway → Kokoro OK" || echo "❌ Gateway → Kokoro FAIL"

docker exec voice-gateway sh -c "curl -s http://ollama:11434/api/tags > /dev/null" && echo "✅ Gateway → Ollama OK" || echo "❌ Gateway → Ollama FAIL"

echo ""
echo "7. Voice Gateway logs (last 10 lines)..."
docker compose logs voice-gateway --tail 10
