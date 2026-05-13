# Voice Services
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/docs/VOICE_SERVICES.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/docs/VOICE_SERVICES.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/docs/VOICE_SERVICES.ca.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/docs/VOICE_SERVICES.zh-cn.md)


This document provides a comprehensive overview of the voice services integrated into the Jules backend.

## Architecture

The voice services consist of three main components:

- **Whisper.cpp**: A high-performance Speech-to-Text (STT) engine.
- **Kokoro-82M**: A fast and natural-sounding Text-to-Speech (TTS) engine.
- **Voice Gateway**: A FastAPI microservice that provides a unified API for voice operations.

## API Documentation

All voice operations are exposed through the Voice Gateway, which runs on port 9000.

### `GET /health`

Returns the health status of the service.

**`curl` example:**
```bash
curl http://localhost:9000/health
```

### `GET /v1/voices`

Lists the available TTS voices.

**`curl` example:**
```bash
curl http://localhost:9000/v1/voices
```

### `GET /v1/models`

Lists the available LLM models.

**`curl` example:**
```bash
curl http://localhost:9000/v1/models
```

### `POST /v1/audio/transcriptions`

Transcribes an audio file.

- **Request**: `multipart/form-data` with an audio file.
- **Response**: A JSON object with the transcribed text.

**`curl` example:**
```bash
curl -X POST -F "file=@test_audio.wav" http://localhost:9000/v1/audio/transcriptions
```

### `POST /v1/audio/speech`

Generates speech from text.

- **Request**: A JSON object with the text to be synthesized.
- **Response**: An audio file in the specified format.

**`curl` example:**
```bash
curl -X POST -H "Content-Type: application/json" -d '{"text":"Hello, world!"}' http://localhost:9000/v1/audio/speech -o test_output.mp3
```

### `POST /v1/conversation`

A full conversation pipeline that takes an audio file, transcribes it, sends the text to an LLM, and synthesizes the response.

- **Request**: `multipart/form-data` with an audio file and the name of the LLM model to use.
- **Response**: A JSON object containing the user's text, the AI's text, and the synthesized audio in base64 format.

**`curl` example:**
```bash
curl -X POST -F "file=@test_audio.wav" -F "model=llama3.2" http://localhost:9000/v1/conversation
```

## Configuration Options

The voice services can be configured using the following environment variables in the `.env` file:

- `WHISPER_MODEL`: The Whisper model to use for STT (e.g., `base.en`, `tiny.en`).
- `KOKORO_VOICE`: The default voice to use for TTS.
- `KOKORO_COMPUTE_TYPE`: The compute type for Kokoro TTS (e.g., `float16`, `float32`).
- `VOICE_GATEWAY_PORT`: The port for the Voice Gateway.
- `VOICE_CACHE_TTL`: The time-to-live for the TTS cache in seconds.

## Hardware Requirements

- **CPU**: A modern CPU with at least 4 cores is recommended.
- **GPU**: For GPU acceleration, an NVIDIA GPU with at least 6GB of VRAM is recommended.

## Performance Benchmarks

- **STT Latency**: <2s for 10s of audio (GPU)
- **TTS Latency**: <0.5s for 50 words (GPU)
- **Full Pipeline**: <5s end-to-end (GPU)

## Troubleshooting

- **"Port already in use" error**: Stop any other services that may be using ports 8080, 8880, or 9000.
- **High latency**: Ensure that you are using the GPU profile if you have a compatible NVIDIA GPU.
- **Model download failures**: Check your internet connection and ensure that you can access huggingface.co.
- **`ffmpeg: command not found`**: The `test-voice-api.sh` script requires `ffmpeg` to be installed. You can install it with `sudo apt-get install ffmpeg` on Debian-based systems.

## Usage

The voice services can be deployed using the following commands:

- **GPU**: `docker compose --profile gpu-nvidia --profile voice up -d`
- **CPU**: `docker compose --profile voice-cpu up -d`
