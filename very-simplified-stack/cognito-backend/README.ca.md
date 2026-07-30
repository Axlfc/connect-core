# 🧠 Cognito Backend AI — Uncertainty-Aware API
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/very-simplified-stack/cognito-backend/README.ca.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/very-simplified-stack/cognito-backend/README.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/very-simplified-stack/cognito-backend/README.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/very-simplified-stack/cognito-backend/README.zh-cn.md)

Aquest backend proporciona una API compatible amb OpenAI amb **puntuació d'incertesa** addicional per a models basats en Ollama. Inclou un perfil de PowerShell amb renderitzat de tokens codificat per colors (blau → àmbar → vermell) basat en el nivell de confiança del model.

## 🚀 Característiques Clau

- **Monitoratge d'Incertesa**: Càlcul en temps real de l'entropia de Shannon token per token.
- **Enriquiment de Streaming SSE**: Injecta puntuacions d'`uncertainty` (incertesa) en els fragments de streaming compatibles amb OpenAI.
- **PowerShell CLI**: Ordres integrades `cog` (text) i `cogt` (veu) amb retroalimentació visual acolorida.
- **Enrutament Multi-Backend**: Lògica de failover en cascada (GPU primer) amb enrutament basat en prioritats.

## 🛠️ Instal·lació

### 1. Backend (Python/FastAPI)
El backend s'executa habitualment mitjançant Docker Compose com a part de `very-simplified-stack`. Assegura't de tenir accés a una instància d'Ollama (per defecte: `http://192.168.1.15:11434`).

### 2. Perfil de PowerShell (Client)
Per instal·lar les eines de línia d'ordres (`cog`, `cogt`) i habilitar la visualització d'incertesa:

1. Obre PowerShell.
2. Navega a aquest directori.
3. Executa l'instal·lador:
   ```powershell
   .\Install-CognitoProfile.ps1
   ```
4. Reinicia PowerShell.

## 🎨 Visualización d'Incertesa

El CLI utilitza la següent escala de colors per indicar la confiança del model:
- 🔵 **Blau** (baixa incertesa, alta confiança)
- 🟡 **Àmbar** (incertesa mitjana, vacil·lació lleu)
- 🔴 **Vermell** (alta incertesa, possible al·lucinació o raonament complex)

### Paràmetres d'Ordre

- `-Threshold 0.6`: Sobreescriu el llindar d'incertesa per defecte per al acolorit.
- `-NoColor`: Desactiva tot el acolorit per a la petició actual (útil per a les canonades/piping).
- `-NoTTS`: (per a `cogt`) Desactiva la lectura de text a veu per a la petició actual.

## ⚙️ Configuració

La configuració es carrega en el següent ordre estricte de prioritat:
1. **Paràmetres de línia d'ordres** (ex. `-Threshold`)
2. **Variables d'entorn**:
   - `COGNITO_UNCERTAINTY_THRESHOLD` (per defecte: `0.55`)
   - `COGNITO_ENABLE_UNCERTAINTY` (`true`/`false`)
   - `COGNITO_COLOR_MODE` (`full`, `threshold` o `none`)
3. **Fitxer de configuració**: `~/.cognito/config.json`
4. **Ajustos per defecte**

## 📂 Estructura del Projecte

- `app/api/routes/openai_compat.py`: Lògica central de streaming i càlcul d'incertesa.
- `app/services/backend_client.py`: Client asíncron unificat per a backends Ollama i OpenAI.
- `app/core/agent_loop.py`: Converteix la generació de text en un bucle d'agent d'execució d'eines.
- `app/core/session_manager.py`: Persistència i gestió d'historial per a sessions d'IA.
- `cli/cognito_cli.py`: Client CLI de Python per a l'Agent Cognito.
- `app/core/extensions/`: Sistema per carregar i gestionar extensions.
- `app/services/escalation_routing.py`: Mapeig d'escalat de subtasques basat en incertesa.
- `test-voice-api.ps1`: El script de perfil de PowerShell principal que conté `cog` y `cogt`.
- `Install-CognitoProfile.ps1`: Instal·lador per a l'entorn de PowerShell.
- `config.example.json`: Plantilla per al fitxer de configuració de l'usuari.

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
Detecta automàticament si una subtarea s'ha generat com una incertesa inacceptablement alta i l'escala de manera transparent cap a models de major capacitat de raonament.

- **Llindar d'Escalat**: Parametritzable via `COGNITO_ESCALATION_UNCERTAINTY_THRESHOLD` (default: 0.6).
- **Ruta d'Escalat**: Definit a `app/services/escalation_routing.py`.

## 🧪 Proves

Per provar les funcions d'incertesa:
```powershell
# Només text
cog "What is the meaning of life?"

# Veu + Text amb un llindar personalitzat
cogt "Explain quantum entanglement in one sentence." -Threshold 0.4
```

Per verificar la compatibilitat cap enrere (utilitzant un backend sense incertesa):
```powershell
cog "Test message" -Endpoint "http://external-openai-backend/v1/chat/completions"
```
El resultat hauria de renderitzar-se en text estàndard blanc/gris sense errors.
