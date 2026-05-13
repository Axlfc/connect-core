# 🧠 Cognito Backend AI — Uncertainty-Aware API
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/cognito-stack/blob/master/very-simplified-stack/cognito-backend/README.ca.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/cognito-stack/blob/master/very-simplified-stack/cognito-backend/README.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/cognito-stack/blob/master/very-simplified-stack/cognito-backend/README.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/cognito-stack/blob/master/very-simplified-stack/cognito-backend/README.zh-cn.md)


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
