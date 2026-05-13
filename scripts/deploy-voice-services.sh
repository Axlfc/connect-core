#!/bin/bash

# This script automates the deployment of the voice services.

# Detect GPU
if nvidia-smi &> /dev/null; then
  echo "NVIDIA GPU detected. Using GPU profile."
  PROFILE="--profile gpu-nvidia --profile voice"
  WHISPER_SERVICE="whisper-stt"
  KOKORO_SERVICE="kokoro-tts"
else
  echo "No NVIDIA GPU detected. Using CPU profile."
  PROFILE="--profile voice-cpu"
  WHISPER_SERVICE="whisper-stt-cpu"
  KOKORO_SERVICE="kokoro-tts-cpu"
fi

# Deploy services
docker compose $PROFILE up -d

# Health checks
echo "Waiting for services to be healthy..."
SERVICES=("$WHISPER_SERVICE" "$KOKORO_SERVICE" "voice-gateway")
for SERVICE in "${SERVICES[@]}"; do
  until [ "$(docker inspect -f {{.State.Health.Status}} $SERVICE)" = "healthy" ]; do
    sleep 1
  done
  echo "$SERVICE is healthy."
done

echo "All voice services are deployed and healthy."
