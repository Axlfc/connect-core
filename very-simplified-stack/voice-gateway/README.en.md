# Voice Gateway
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/cognito-stack/blob/master/very-simplified-stack/voice-gateway/README.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/cognito-stack/blob/master/very-simplified-stack/voice-gateway/README.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/cognito-stack/blob/master/very-simplified-stack/voice-gateway/README.ca.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/cognito-stack/blob/master/very-simplified-stack/voice-gateway/README.zh-cn.md)


This is a FastAPI microservice that acts as a unified gateway for voice operations, including Speech-to-Text (STT) and Text-to-Speech (TTS).

## Endpoints

- `GET /health`: Health check endpoint.
- `GET /v1/voices`: Lists available TTS voices.
- `GET /v1/models`: Lists available LLM models.
- `POST /v1/audio/transcriptions`: Transcribes an audio file.
- `POST /v1/audio/speech`: Generates speech from text.
- `POST /v1/conversation`: Full conversation pipeline (STT -> LLM -> TTS).

## Running the Service

The service is intended to be run as a Docker container, orchestrated by the main `docker-compose.yml` file in the root of the repository.
