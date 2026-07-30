# 🧠 Very Simplified AI Stack — Lightweight Cognitive Platform
[![en](https://img.shields.io/badge/lang-en-red.svg)](README.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](README.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](README.ca.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](README.zh-cn.md)

This is a refined, "very simplified" version of the AI Stack. It is designed for users who want the core orchestration capabilities and local cognitive AI tools but prefer to run their LLMs (such as Ollama) externally or on another dedicated host machine.

The core of this simplified stack centers on the **Cognito Agent**, natively integrating the **NOOA (NVIDIA-labs Object Oriented Agents)** paradigm and the 5 phases of the AGI Agents Roadmap.

---

## 🚀 What's Included?

- **PostgreSQL**: Relational database with integrated vector extension (`pgvector`).
- **Qdrant**: High-performance vector database for semantic search and RAG pipelines.
- **Redis**: Ultra-fast in-memory caching for session and agent state management.
- **Forgejo**: Self-hosted Git service to manage repositories, code, and webhooks.
- **ComfyUI**: Advanced AI image generation with native Stable Diffusion support.
- **Voice Services**: High-performance integration of Whisper (STT), Kokoro (TTS), and Demucs (audio separation).
- **Voice Gateway**: Unified API and gateway for all voice-related processing tasks.
- **Nginx Proxy & zrok**: Flexible reverse proxy and secure tunneling for public webhooks.
- **Cognito Backend (`cognito-backend`)**: Intelligent control plane, multi-model AI router, and agent loop orchestrator.
- **Cognito Worker (`cognito-worker`)**: Host-side secure execution component executing git worktrees, compiling code, and verifying proposed patches.

---

## ❌ What was removed?

To keep this stack as slim and agile as possible, we have removed:
- **Obsidian**: Local knowledge base management.
- **Drupal**: CMS / Web UI experimentation layer.
- **Monitoring**: Prometheus, Grafana, Alertmanager, etc.
- **Support Tools**: LibreTranslate, LanguageTool, Duplicati, Uptime Kuma.

---

## 🤖 Cognito Agent Architecture Deep-Dive

The stack's intelligence is distributed across two highly robust native components:

### 1. Control Plane: `cognito-backend`
Developed in FastAPI, the backend acts as the brain of the orchestrator:
- **Agent Loop (SSE)**: Exposes the `/api/agent/loop` endpoint executing interactive reasoning and async tool calls.
- **NOOAMeta Metaclass**: Automatically wraps abstract methods declared with ellipsis (`...`) into structured LLM completions, strictly enforcing Pydantic contracts.
- **Selective Visibility**: Omit methods/attributes decorated with `@hidden` or private prefixes from the LLM prompt.
- **Auto-Compaction**: Summarizes historical context on-the-fly when session exceeds maximum context window tokens.
- **Uncertainty-Based Escalation**: If the active model generates subtasks with high Shannon entropy, the orchestrator automatically escalates them to high-capacity models (e.g., GPT-4o, Claude) to ensure output quality.

### 2. Execution Plane: `cognito-worker`
Running securely on the host, the python-based worker handles heavy workspace tasks:
- **Git Worktree Isolation**: Securely clones the target repository on separate temporary worktrees to compile and test agent proposed patches without altering the user's active branch.
- **HMAC Cryptographic Validation**: Signs and validates all request payloads using a shared HMAC secret, preventing request tampering and replay attacks.
- **Sandboxing SandboxExecutor**: Monitored Python subprocess execution applying CPU, memory limits, and rigid execution timeouts.

---

## 🛠️ Getting Started (Installation & Launch)

> **Note**: This stack assumes you have [Ollama](https://ollama.com/) running externally (e.g., on your host machine or another server). By default, it is preconfigured to connect to `http://host.docker.internal:11434`.

### Step 1: Configure Environment Variables
Copy the template and set up your passwords and secrets in the `.env` file:
```bash
cp .env.example .env
nano .env
```
Ensure you update the `OLLAMA_API_URL` and `OLLAMA_URL` variables pointing to your external Ollama instance.

### Step 2: Start the Stack
Select the execution command matching your hardware specifications:

- **CPU Mode (No GPU)**:
  ```bash
  docker compose --profile cpu --profile voice-cpu up -d
  ```

- **NVIDIA GPU Mode**:
  ```bash
  docker compose --profile gpu-nvidia --profile voice up -d
  ```

- **With Public zrok Tunneling**:
  Append `--profile zrok` to your startup command.

### Step 3: Run the Cognito Worker on Host (Optional for agent execution)
To activate the host-side workspace execution daemon:
```bash
cd cognito-worker
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn worker_app.main:app --host 0.0.0.0 --port 8001
```

---

## 💡 What Can We Do With This Setup?

With this stack running, you have an extremely powerful cognitive AI environment capable of:

1. **Deploying Autonomous Code-Writing Agents**:
   Use `cognito-backend`'s API or the lightweight Python CLI (`python -m cli.cognito_cli`) to chat with your local workspace. The agent can read, write, edit files, or execute bash commands safely respecting file protections and repository trust parameters.
2. **Executing 5-Phase AGI Workflows**:
   Utilize the `agents/` module to break down complex tasks (Phase 1: Chain-of-Thought), validate outcomes with iterative feedback loops (Phase 2), learn from past experiences (Phase 3), coordinate multi-agent routing (Phase 4), and optimize resource allocations (Phase 5).
3. **Semantic Search & RAG**:
   Ingest architecture diagrams, threat models, or local markdown files into Qdrant, allowing your agent to answer complex questions with context retrieved in real time.
4. **Local Audio & Speech Processing**:
   Convert text to audio with Kokoro TTS, transcribe audio with Whisper STT, or split vocal tracks with Demucs using the unified Voice Gateway.
