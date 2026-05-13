#!/bin/bash

# This script runs a comprehensive suite of tests for the voice API.

# Check for ffmpeg and install if not present
if ! command -v ffmpeg &> /dev/null
then
    echo "ffmpeg could not be found, attempting to install..."
    sudo apt-get update && sudo apt-get install -y ffmpeg
fi


# Generate test audio
ffmpeg -f lavfi -i "anoisesrc=a=0.1:c=white:d=5" -y test_audio.wav

# Test STT endpoint and measure latency
echo "Testing STT endpoint..."
time curl -X POST -F "file=@test_audio.wav" http://localhost:9000/v1/audio/transcriptions

# Test TTS endpoint and measure latency
echo "Testing TTS endpoint..."
time curl -X POST -H "Content-Type: application/json" -d '{"text":"Hello, world!"}' http://localhost:9000/v1/audio/speech -o test_output.mp3

# Test full conversation pipeline and measure latency
echo "Testing full conversation pipeline..."
time curl -X POST -F "file=@test_audio.wav" -F "model=llama3.2" http://localhost:9000/v1/conversation

# Simple load test (10 concurrent requests to TTS)
echo "Running simple load test on TTS endpoint..."
for i in {1..10}; do
  curl -X POST -H "Content-Type: application/json" -d '{"text":"Hello, world!"}' http://localhost:9000/v1/audio/speech -o /dev/null &
done
wait

# Clean up
rm test_audio.wav test_output.mp3

echo "All tests complete."
