# Simplified Isolated AI Stack with Drupal, Obsidian & Forgejo
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/simplified-stack/README.ca.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/simplified-stack/README.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/simplified-stack/README.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/simplified-stack/README.zh-cn.md)


This project provides a secondary simplified Docker Compose setup for an isolated AI workflow. It uses **Drupal** as the main orchestration system, **Obsidian** for knowledge management, and **Forgejo** for self-hosted Git services.

## 🚀 Components

1.  **Drupal 10**: The central orchestration system, managing content, users, and coordinating AI workflows.
2.  **Obsidian**: A powerful knowledge base that works on top of a local folder of plain text Markdown files, accessible via a web interface.
3.  **Forgejo**: A lightweight, self-hosted Git service to manage code and workflow versions.
4.  **Qdrant**: High-performance vector database for RAG (Retrieval-Augmented Generation) and similarity search.
5.  **PostgreSQL 16 (pgvector)**: Relational database with vector similarity search capabilities, shared by Drupal, n8n, and Forgejo.
6.  **ComfyUI**: Advanced node-based GUI for Stable Diffusion image generation.
7.  **n8n**: Workflow automation platform with support for external Python and JavaScript task runners.
8.  **n8n-runner**: Isolated execution environment for n8n's Python and JavaScript code nodes.
9.  **Ollama**: Local LLM engine for running models like Llama 3, Mistral, and others.

## 📂 Project Structure

```text
simplified-stack/
├── comfyui/            # ComfyUI Docker configuration
├── data/               # Persistent data stored via bind mounts
├── drupal/             # Drupal configuration placeholders
├── forgejo/            # Forgejo configuration placeholders
├── n8n/                # n8n runner configuration
├── ollama/             # Ollama Docker configuration
├── obsidian/           # Obsidian configuration placeholders
├── postgres/           # Database initialization scripts
├── qdrant/             # Qdrant configuration
├── shared/             # Shared volume for inter-service data exchange
├── .env.example        # Template for environment variables
└── docker-compose.yml  # Main service orchestration file
```

## 🛠️ Getting Started

### 1. Prerequisites
- Docker and Docker Compose installed.
- **NVIDIA GPU**: Install [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html).
- **AMD GPU**: Ensure ROCm drivers are installed on the host.

### 2. Configuration
Run the setup script to generate your `.env` file with secure random keys:
```bash
bash scripts/setup-env.sh
```

### 3. Launching Services

Use the provided `start.sh` script to launch services by groups and hardware.

**Base AI Stack (Minimal):**
Includes n8n, runners, qdrant, postgres, redis, and ollama.
```bash
./scripts/start.sh --minimal --nvidia  # For NVIDIA
./scripts/start.sh --minimal --amd     # For AMD
./scripts/start.sh --minimal --cpu     # For CPU only
```

**Launch Everything:**
```bash
./scripts/start.sh --all --nvidia
```

**Custom Combinations:**
```bash
./scripts/start.sh --minimal --cms --git --nvidia
```

**Available Group Flags:**
- `--minimal`: Core AI components (Base).
- `--cms`: Drupal orchestration.
- `--git`: Forgejo Git hosting.
- `--knowledge`: Obsidian knowledge management.
- `--creative`: ComfyUI image generation.

**Stopping Services:**
```bash
./scripts/stop.sh
```

## 🛠️ Maintenance & Troubleshooting

- **Check Status**: `./scripts/troubleshoot.sh`
- **Logs**: `docker compose logs -f [service_name]`
- **Reset Environment**: `./scripts/stop.sh && rm .env` (⚠️ Deletes config, not data)

## 🔌 Component Interaction

- **Drupal** is the primary orchestrator for content and user management.
- **Obsidian** provides a web-accessible interface to manage the knowledge base (Markdown files) stored in the `shared` volume.
- **Forgejo** allows for version control of scripts, n8n workflows (via export), and Drupal configuration.
- **n8n** executes background tasks, connecting all services.
- **n8n-runner** ensures secure script execution.
- **Ollama** provides local LLM capabilities for text generation and embeddings.
- **ComfyUI** handles AI image generation.
- **Shared Volume**: All services (including Obsidian and Drupal) have access to `./shared/`, allowing them to collaborate on the same set of files.

## 🔒 Security & Performance

- **Network Isolation**: Services are split into `frontend`, `backend`, and `ai` networks.
- **Resource Limits**: Each service has defined CPU and memory limits.
- **Non-root Users**: Configured where supported.
- **GPU Optimization**: Pre-configured for efficiency.
- **Data Persistence**: Uses bind mounts in `./data` for easy visibility and backups.

## 📝 Notes
- **Permissions**: Since this setup uses bind mounts, you may need to adjust ownership of the `./data` and `./shared` directories:
  ```bash
  sudo chown -R 1000:1000 ./data ./shared
  ```
- **Forgejo Access**: Accessible via http://localhost:3002.
- **Obsidian Access**: Accessible via http://localhost:3000 (Web interface).
- **Drupal Setup**: Follow the installation wizard at http://localhost:8080.
- **Initial Setup**: ComfyUI will download models on first run.
