# 🧠 Cognito Backend AI — Uncertainty-Aware API
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/very-simplified-stack/cognito-backend/README.ca.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/very-simplified-stack/cognito-backend/README.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/very-simplified-stack/cognito-backend/README.md)
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

## 🤖 Agent Cognito (Fase 1)

El backend ara inclou suport natiu per a agents autònoms capaços d'executar eines del sistema i locals.

### Endpoints
- `POST /api/agent/loop`: Endpoint SSE que executa el bucle de raonament i execució d'eines.
  - **Body**: `{ "messages": [...], "cwd": "path/to/repo", "model_params": {} }`
  - **Esdeveniments**: `text_delta`, `tool_call`, `tool_result`, `done`, `error`.

### Sessions i Persistència (Fase 2)
Les converses es guarden a `~/.cognito/sessions/` en format JSONL (append-only) amb un índex global a `index.json`.

- **Compactat Automàtic**: Quan una sessió supera el límit màxim de tokens (default: 8000), el sistema genera automàticament un resum i compacta l'historial.
- **Continuïtat**: Passa `session_id: "latest"` per continuar la sessió més recent sota el `cwd` actual.
- **Forking**: Permet clonar una sessió existent per explorar branques alternatives de raonament.

### CLI de Python (Fase 3)
S'inclou un client de línia de comandes de Python amb tres modes de funcionament:

- **Mode `print`** (default): Sortida intermitent de paraules en temps real pintades amb colors ANSI TrueColor segons la incertesa de Shannon.
  ```bash
  python -m cli.cognito_cli "Explica la fotosíntesi" --session-id latest
  ```
- **Mode `json`**: Sortida estructurada en format NDJSON per a canalitzacions o scripts.
  ```bash
  python -m cli.cognito_cli "Llista fitxers del repositori" --mode json
  ```
- **Mode `rpc`**: Interfície JSON-RPC 2.0 sobre stdin/stdout per a automatitzacions complexes de llarga durada.
  ```bash
  python -m cli.cognito_cli --mode rpc
  ```

### Eines Disponibles
1. `read`: Lectura segura de fitxers continguts estrictament dins del directori de treball (`cwd`).
2. `write`: Creació o escriptura segura de fitxers (requereix confiança `trust`).
3. `edit`: Editor quirúrgic basat en blocs de cerca i reemplaçament (requereix `trust`).
4. `bash`: Execució de comandes bash no privilegiades (requereix `trust`, sense `sudo`).

### Seguretat i Confiança
- **Fitxers Protegits**: Certs fitxers d'alta prioritat i credencials (p. ej. `auth.js`) estan totalment protegits contra escriptures o modificacions.
- **Project Trust**: Les eines destructives d'escriptura o execució de terminals requereixen que el directori hagi estat marcat expressament com a confiable.
- **AGENTS.md**: Si existeix un fitxer d'instruccions d'agent a la de l'arrel de `cwd`, s'injecta automàticament com a context d'alt rang del sistema.

### Sistema d'Extensions (Fase 4)
Permet estendre les funcionalitats de l'agent en temps d'execució mitjançant mòduls personalitzats de Python carregats dinàmicament.

- **Àmbits**: Global (`~/.cognito/extensions/`), Configuració (`config.json`), i Local del Projecte (`.cognito/extensions/`).
- **Capacitats**: Afegir eines personalitzades, rutes del orquestrador, i subscriure's a esdeveniments (hooks).

### Escalabilitat Adaptativa (Fase 5)
Detecta automàticament si una subtarea s'ha generat amb una incertesa inacceptablement alta i l'escala de manera transparent cap a models de major capacitat de raonament.

- **Llindar d'Escalat**: Parametritzable via `COGNITO_ESCALATION_UNCERTAINTY_THRESHOLD` (default: 0.6).
- **Ruta d'Escalat**: Definit a `app/services/escalation_routing.py`.

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
