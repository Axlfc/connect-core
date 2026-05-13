# Very Simplified AI Stack
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/cognito-stack/blob/master/very-simplified-stack/README.ca.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/cognito-stack/blob/master/very-simplified-stack/README.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/cognito-stack/blob/master/very-simplified-stack/README.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/cognito-stack/blob/master/very-simplified-stack/README.zh-cn.md)


This is a refined, "very simplified" version of the AI Stack. It is designed for users who want the core orchestration and AI tools but prefer to run LLMs (Ollama) externally or on a different machine.

## 🚀 What's Included?

- **PostgreSQL**: Vector-enabled database (pgvector).
- **Qdrant**: High-performance vector database.
- **Redis**: Fast caching and session management.
- **Forgejo**: Self-hosted Git service for managing your code and workflows.
- **ComfyUI**: Advanced AI image generation.
- **Voice Services**: Whisper (STT), Kokoro (TTS), and Demucs (Audio Separation).
- **Voice Gateway**: Unified API for all voice-related tasks.
- **Cognito Backend**: A reasoning-capable AI Agent API.
- **Nginx Proxy & zrok**: Flexible external access and SSL management.

## ❌ What was removed?

To keep it as slim as possible, we've removed:
- **Obsidian**: Local knowledge management.
- **Drupal**: CMS / UI experimentation layer.
- **Monitoring**: Prometheus, Grafana, Alertmanager, etc.
- **Other tools**: LibreTranslate, LanguageTool, Duplicati, Uptime Kuma.

## 🛠️ Getting Started

> **Note**: This stack assumes you have [Ollama](https://ollama.com/) running externally (e.g., on your host machine or another server). By default, it's configured to connect to `http://host.docker.internal:11434`.

1.  **Copy Environment Variables**:
    ```bash
    cp .env.example .env
    ```
    Edit `.env` to set your passwords, keys, and specifically `OLLAMA_API_URL` and `OLLAMA_URL` pointing to your external Ollama instance if it's not the default.

2.  **Start the Stack**:
    - **CPU Mode**:
      ```bash
      docker compose --profile cpu --profile voice-cpu up -d
      ```
    - **NVIDIA GPU Mode**:
      ```bash
      docker compose --profile gpu-nvidia --profile voice up -d
      ```
    - **With zrok Tunneling**:
      Add `--profile zrok` to your command.

3.  **Access Services**:
    - Forgejo: [http://localhost:3002](http://localhost:3002)
    - ComfyUI: [http://localhost:8188](http://localhost:8188)
    - Qdrant: [http://localhost:6333/dashboard](http://localhost:6333/dashboard)
    - Cognito API: [http://localhost:8000/docs](http://localhost:8000/docs)
