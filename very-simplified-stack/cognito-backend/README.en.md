# 🧠 Cognito Backend AI — Uncertainty-Aware API
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/very-simplified-stack/cognito-backend/README.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/very-simplified-stack/cognito-backend/README.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/very-simplified-stack/cognito-backend/README.ca.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/very-simplified-stack/cognito-backend/README.zh-cn.md)


This backend provides an OpenAI-compatible API with additional **uncertainty scoring** for Ollama-based models. It includes a PowerShell profile with color-coded token rendering (blue → amber → red) based on the model's confidence level.

## 🚀 Key Features

- **Uncertainty Monitoring**: Real-time calculation of token-by-token Shannon entropy.
- **SSE Streaming Enrichment**: Injects `uncertainty` scores into standard OpenAI-compatible chunks.
- **PowerShell CLI**: Integrated `cog` (text) and `cogt` (voice) commands with visual feedback.
- **Multi-Backend Routing**: Cascading failover logic (GPU-first) with priority-based routing.

## 🛠️ Installation

### 1. Backend (Python/FastAPI)
The backend is typically run via Docker Compose as part of the `very-simplified-stack`.
Ensure you have access to an Ollama instance (default: `http://192.168.1.15:11434`).

### 2. PowerShell Profile (Client)
To install the CLI tools (`cog`, `cogt`) and enable uncertainty visualization:

1. Open PowerShell.
2. Navigate to this directory.
3. Run the installer:
   ```powershell
   .\Install-CognitoProfile.ps1
   ```
4. Restart PowerShell.

## 🎨 Uncertainty Visualization

The CLI uses the following color gradient to indicate model confidence:
- 🔵 **Blue** (low uncertainty, high confidence)
- 🟡 **Amber** (medium uncertainty, mild hesitation)
- 🔴 **Red** (high uncertainty, potential hallucination or complex reasoning)

### Command Parameters

- `-Threshold 0.6`: Override the default uncertainty threshold for coloring.
- `-NoColor`: Disable all coloring for the current request (useful for piping output).
- `-NoTTS`: (for `cogt`) Disable text-to-speech for the current request.

## ⚙️ Configuration

Settings are loaded in the following order of priority:
1. **Command Line Parameters** (e.g., `-Threshold`)
2. **Environment Variables**:
   - `COGNITO_UNCERTAINTY_THRESHOLD` (default: `0.55`)
   - `COGNITO_ENABLE_UNCERTAINTY` (`true`/`false`)
   - `COGNITO_COLOR_MODE` (`full`, `threshold`, or `none`)
3. **Configuration File**: `~/.cognito/config.json`
4. **Default Settings**

## 📂 Project Structure

- `app/api/routes/openai_compat.py`: Core streaming and uncertainty calculation logic.
- `app/services/backend_client.py`: Unified async client for Ollama and OpenAI backends.
- `test-voice-api.ps1`: The main PowerShell profile script containing `cog` and `cogt`.
- `Install-CognitoProfile.ps1`: Installer for the PowerShell environment.
- `config.example.json`: Template for the user configuration file.

## 🤖 Cognito Agent (Phase 1)

The backend now includes native support for autonomous agents capable of calling system and local tools.

### Endpoints
- `POST /api/agent/loop`: SSE endpoint that executes the reasoning and tool execution loop.
  - **Body**: `{ "messages": [...], "cwd": "path/to/repo", "model_params": {} }`
  - **Events**: `text_delta`, `tool_call`, `tool_result`, `done`, `error`.

### Sessions & Persistence (Phase 2)
Conversations are persisted in `~/.cognito/sessions/` as append-only JSONL files with a global index in `index.json`.

- **Auto-Compaction**: When a session exceeds the maximum token limit (default: 8000), the system triggers compaction by generating a summary and clearing historical context.
- **Continuity**: Pass `session_id: "latest"` to dynamically pick up and continue the most recent session under the specified `cwd`.
- **Forking**: Allows cloning an existing session to explore alternative execution branches without altering the original timeline.

### Python CLI (Phase 3)
A lightweight command-line Python client is included with three specialized modes:

- **`print` Mode** (default): Streamed delta outputs mapped in real-time with TrueColor ANSI colors based on Shannon entropy.
  ```bash
  python -m cli.cognito_cli "Explain photosynthesis" --session-id latest
  ```
- **`json` Mode**: Formatted NDJSON output for seamless integration with downstream shell tools and pipelines.
  ```bash
  python -m cli.cognito_cli "List workspace files" --mode json
  ```
- **`rpc` Mode**: JSON-RPC 2.0 interface over stdin/stdout, ideal for integration with persistent processes.
  ```bash
  python -m cli.cognito_cli --mode rpc
  ```

### Available Tools
1. `read`: Safe read file utility strictly contained under the workspace root (`cwd`).
2. `write`: Safe creation and overwrite tool (requires project `trust`).
3. `edit`: Block-based search-and-replace editor (requires project `trust`).
4. `bash`: Execute non-privileged bash commands (requires project `trust`, forbids `sudo`).

### Security and Trust
- **Protected Files**: High-priority credential or auth files (e.g. `auth.js`) are protected from edits or writes.
- **Project Trust**: Destructive and write-based tools require active project workspace trust endorsement.
- **AGENTS.md**: Automatically inyected and merged as high-priority system context when detected under the `cwd`.

### Extension System (Phase 4)
Provides seamless extensibility without modifications to source files via custom Python plug-in modules loaded at runtime.

- **Scopes**: Global (`~/.cognito/extensions/`), Config (`config.json`), and Project Local (`.cognito/extensions/`).
- **Capabilites**: Register tools, customized routing, backends, and subscribe to events (hooks).

### Adaptive Escalation (Phase 5)
Detects subtasks generated with high uncertainty and automatically escalates them to higher-capacity LLM models.

- **Escalation Threshold**: Controlled via `COGNITO_ESCALATION_UNCERTAINTY_THRESHOLD` (default: 0.6).
- **Escalation Router**: Configured under `app/services/escalation_routing.py`.

## 🧪 Testing

To test the uncertainty features:
```powershell
# Text only
cog "What is the meaning of life?"

# Voice + Text with a custom threshold
cogt "Explain quantum entanglement in one sentence." -Threshold 0.4
```

To verify backward compatibility (using a backend without uncertainty):
```powershell
cog "Test message" -Endpoint "http://external-openai-backend/v1/chat/completions"
```
The output should be rendered in standard white/gray text without errors.
