# 🧠 Cognito Backend AI — Uncertainty-Aware API
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/very-simplified-stack/cognito-backend/README.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/very-simplified-stack/cognito-backend/README.en.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/very-simplified-stack/cognito-backend/README.ca.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/very-simplified-stack/cognito-backend/README.zh-cn.md)

Este backend proporciona una API compatible con OpenAI con **puntuación de incertidumbre** adicional para modelos basados en Ollama. Incluye un perfil de PowerShell con renderizado de tokens codificado por colores (azul → ámbar → rojo) basado en el nivel de confianza del modelo.

## 🚀 Características Clave

- **Monitoreo de Incertidumbre**: Cálculo en tiempo real de la entropía de Shannon token por token.
- **Enriquecimiento de Streaming SSE**: Inyecta puntuaciones de `uncertainty` (incertidumbre) en los fragmentos de streaming compatibles con OpenAI.
- **PowerShell CLI**: Comandos integrados `cog` (texto) y `cogt` (vídeo/voz) con retroalimentación visual coloreada.
- **Enrutamiento Multi-Backend**: Lógica de failover en cascada (GPU primero) con enrutamiento basado en prioridades.

## 🛠️ Instalación

### 1. Backend (Python/FastAPI)
El backend se ejecuta habitualmente mediante Docker Compose como parte de `very-simplified-stack`. Asegúrate de tener acceso a una instancia de Ollama (por defecto: `http://192.168.1.15:11434`).

### 2. Perfil de PowerShell (Cliente)
Para instalar las herramientas de línea de comandos (`cog`, `cogt`) y habilitar la visualización de incertidumbre:

1. Abre PowerShell.
2. Navega a este directorio.
3. Ejecuta el instalador:
   ```powershell
   .\Install-CognitoProfile.ps1
   ```
4. Reinicia PowerShell.

## 🎨 Visualización de Incertidumbre

El CLI utiliza la siguiente escala de colores para indicar la confianza del modelo:
- 🔵 **Azul** (baja incertidumbre, alta confianza)
- 🟡 **Ámbar** (incertidumbre media, vacilación leve)
- 🔴 **Rojo** (alta incertidumbre, posible alucinación o razonamiento complejo)

### Parámetros de Comando

- `-Threshold 0.6`: Sobrescribe el umbral de incertidumbre por defecto para el coloreado.
- `-NoColor`: Desactiva todo el coloreado para la petición actual (útil para tuberías/piping).
- `-NoTTS`: (para `cogt`) Desactiva la lectura de texto a voz para la petición actual.

## ⚙️ Configuración

La configuración se carga en el siguiente orden estricto de prioridad:
1. **Parámetros de línea de comandos** (ej. `-Threshold`)
2. **Variables de entorno**:
   - `COGNITO_UNCERTAINTY_THRESHOLD` (por defecto: `0.55`)
   - `COGNITO_ENABLE_UNCERTAINTY` (`true`/`false`)
   - `COGNITO_COLOR_MODE` (`full`, `threshold` o `none`)
3. **Archivo de configuración**: `~/.cognito/config.json`
4. **Ajustes por defecto**

## 📂 Estructura del Proyecto

- `app/api/routes/openai_compat.py`: Lógica central de streaming y cálculo de incertidumbre.
- `app/services/backend_client.py`: Cliente asíncrono unificado para backends Ollama y OpenAI.
- `app/core/agent_loop.py`: Convierte la generación de texto en un bucle de agente de ejecución de herramientas.
- `app/core/session_manager.py`: Persistencia y gestión de historial para sesiones de IA.
- `cli/cognito_cli.py`: Cliente CLI de Python para el Agente Cognito.
- `app/core/extensions/`: Sistema para cargar y gestionar extensiones.
- `app/services/escalation_routing.py`: Mapeo de escalado de subtareas basado en incertidumbre.
- `test-voice-api.ps1`: El script de perfil de PowerShell principal que contiene `cog` y `cogt`.
- `Install-CognitoProfile.ps1`: Instalador para el entorno de PowerShell.
- `config.example.json`: Plantilla para el archivo de configuración del usuario.

## 🤖 Cognito Agent (Fase 1)

El backend ahora incluye soporte para agentes capaces de ejecutar herramientas (tools).

### Endpoints
- `POST /api/agent/loop`: Endpoint SSE que ejecuta un bucle de razonamiento y ejecución de herramientas.
  - **Body**: `{ "messages": [...], "cwd": "path/to/repo", "model_params": {} }`
  - **Eventos**: `text_delta`, `tool_call`, `tool_result`, `done`, `error`.

### Sesiones y Persistencia (Fase 2)
Las sesiones se guardan en `~/.cognito/sessions/` en formato JSONL (append-only) con un índice global en `index.json`.

- **Compactado Automático**: Cuando una sesión supera el umbral de tokens (default 8000), el sistema genera automáticamente un resumen y compacta el historial para liberar ventana de contexto.
- **Continuidad**: Usa `session_id: "latest"` para continuar automáticamente la conversación más reciente en el `cwd` actual.
- **Forking**: Permite clonar una sesión existente para explorar ramas alternativas sin perder el historial original.

### CLI de Python (Fase 3)
El backend incluye un cliente ligero en Python con tres modos de operación:

- **Modo `print`** (default): Salida interactiva con colores ANSI TrueColor por incertidumbre.
  ```bash
  python -m cli.cognito_cli "Explica la fotosíntesis" --session-id latest
  ```
- **Modo `json`**: Salida NDJSON para integración con otros scripts.
  ```bash
  python -m cli.cognito_cli "Lista archivos" --mode json
  ```
- **Modo `rpc`**: JSON-RPC 2.0 sobre stdin/stdout, para integración con procesos de larga duración.
  ```bash
  python -m cli.cognito_cli --mode rpc
  ```

### Gestión de Lockfiles y Dependencias Congeladas (AUD-006)
`cognito-backend` utiliza un archivo `requirements.lock` con hashes criptográficos sha256 fijados para garantizar instalaciones reproducibles e inmunes a ataques en la cadena de suministro.

- **Instalación con validación de hashes**:
  ```bash
  pip install --no-cache-dir --require-hashes -r requirements.lock
  ```
- **Regenerar Lockfile tras modificar `requirements.txt`**:
  ```bash
  uv pip compile --generate-hashes requirements.txt -o requirements.lock
  # O utilizando pip-tools:
  # pip-compile --generate-hashes requirements.txt -o requirements.lock
  ```

### Herramientas Disponibles
1. `read`: Lee archivos del sistema (restringido al `cwd`).
2. `write`: Crea o sobrescribe archivos (requiere `trust`).
3. `edit`: Edición basada en búsqueda y reemplazo único (requiere `trust`).
4. `bash`: Ejecución de comandos en el workspace (requiere `trust`, sin `sudo`).

### Gestión de Secretos y Rotación (AUD-003)
Cognito incluye la abstracción `SecretsProvider` (`app/core/secrets.py`) para gestionar tokens de autenticación y claves API sin almacenarlos en texto plano expuesto y con soporte para rotación sin reinicios de proceso.

- **Proveedores Soportados**:
  - `LocalFileSecretsProvider` (predeterminado): Carga secretos con resolución jerárquica (Variables de entorno -> `~/.cognito/config.json` con permisos `0o600` y directorio `0o700` -> Token efímero autogenerado). Soporta caché en memoria con TTL configurable (`COGNITO_SECRETS_TTL_SECONDS`).
  - `VaultSecretsProvider` (Stub): Implementación stub documentada preparada para HashiCorp Vault / AWS Secrets Manager.
- **Variables de Configuración del Operador**:
  - `COGNITO_SECRETS_PROVIDER`: Selecciona el proveedor (`local` por defecto, o `vault`).
  - `COGNITO_SECRETS_TTL_SECONDS`: Tiempo de vida en segundos de la caché en memoria (por defecto `0`).
  - `VAULT_ADDR`, `VAULT_TOKEN`, `VAULT_SECRET_PATH`: Variables de configuración para activar `VaultSecretsProvider` en un despliegue real.
  - *Nota*: La integración de red en vivo contra una instancia real de HashiCorp Vault / AWS Secrets Manager queda marcada como trabajo de infraestructura de seguimiento pendiente.
- **Endpoint de Recarga en Caliente**:
  - `POST /api/secrets/reload`: Endpoint REST que invalida la caché de secretos para recargar inmediatamente credenciales rotadas externamente sin necesidad de reiniciar el proceso backend.

### Seguridad y Trust
- **Protected Files**: Ciertos archivos críticos (`auth.js`, etc.) nunca pueden ser modificados.
- **Project Trust**: Las herramientas de escritura y ejecución requieren que el directorio haya sido marcado como confiable.
- **AGENTS.md**: Si existe en el raíz del `cwd`, se inyecta automáticamente como contexto del sistema.
- **Sandbox Network Policy (Deny-All por Defecto)**: El sandbox de Bubblewrap bloquea por defecto todo el tráfico de red saliente no autorizado.
- **Lista Blanca de Hosts Configurable (`COGNITO_SANDBOX_ALLOWED_HOSTS`)**: Los operadores pueden autorizar hosts/IPs salientes adicionales sin modificar código mediante la variable de entorno `COGNITO_SANDBOX_ALLOWED_HOSTS` (separados por comas). Por defecto se autorizan automáticamente los endpoints del backend LLM configurado (`BackendRouter`, Ollama local o OpenAI) y `localhost` / `host.docker.internal`.
  ```bash
  export COGNITO_SANDBOX_ALLOWED_HOSTS="api.openai.com,192.168.1.15,custom-llm-host.internal"
  ```

### Sistema de Extensiones (Fase 4)
El sistema permite extender el agente sin modificar el código fuente mediante ficheros Python cargados en runtime.

- **Niveles de Carga**: Global (`~/.cognito/extensions/`), Configurado (`config.json`), y Local al Proyecto (`.cognito/extensions/`).
- **Capacidades**: Registrar herramientas nuevas, backends, intents del orquestador, y suscribirse a eventos (hooks).
- **Seguridad**: Las extensiones locales requieren que el proyecto sea marcado como confiable para extensiones (`set_extensions_trusted`).
  - ⚠️ **ADVERTENCIA**: Marcar un repo con `extensions_trusted=True` concede a ese código el mismo nivel de acceso que el propio proceso del backend. No es un sandbox.

### Escalado Adaptativo (Fase 5)
El orquestador (`cognito-orchestrator`) ahora puede detectar si una subtarea se ha generado con alta incertidumbre y reintentarla automáticamente con un modelo de mayor capacidad.

- **Umbral de Escalado**: configurable vía `COGNITO_ESCALATION_UNCERTAINTY_THRESHOLD` (default: 0.6).
- **Mapeo de Escalado**: Definido en `app/services/escalation_routing.py`. Axel debe revisar este archivo para asegurar que los modelos de destino están disponibles en su entorno.
- **Transparencia**: El escalado es automático y se registra en los logs del servidor. La respuesta final incluye metadatos sobre qué subtareas fueron escaladas.

## 🧪 Pruebas

Para probar las funciones de incertidumbre:
```powershell
# Solo texto
cog "What is the meaning of life?"

# Voz + Texto con un umbral personalizado
cogt "Explain quantum entanglement in one sentence." -Threshold 0.4
```

Para verificar la compatibilidad hacia atrás (usando un backend sin incertidumbre):
```powershell
cog "Test message" -Endpoint "http://external-openai-backend/v1/chat/completions"
```
El resultado debería renderizarse en texto estándar blanco/gris sin errores.
