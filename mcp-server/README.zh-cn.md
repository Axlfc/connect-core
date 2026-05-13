# Servidor MCP de Herramientas del Cognito-Stack
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/mcp-server/README.zh-cn.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/mcp-server/README.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/mcp-server/README.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/mcp-server/README.ca.md)


Este proyecto implementa un servidor [MCP (Model Context Protocol)](https://github.com/anthropics/anthropic-tools) que expone las capacidades del Cognito-Stack como herramientas para clientes compatibles, como Claude Desktop.

El servidor actúa como un puente, permitiendo a un agente de IA orquestar servicios como Ollama, Qdrant, n8n y más.

## 🚀 Inicio Rápido

### 1. Prerrequisitos

- Python 3.10+
- `uv` instalado (`pip install uv`)
- Los servicios del Cognito-Stack (Ollama, Qdrant, etc.) deben estar en ejecución y accesibles desde `localhost`.

### 2. Instalación

1.  **Navega al directorio del servidor:**
    ```bash
    cd mcp-server
    ```

2.  **Crea un entorno virtual e instala las dependencias:**
    ```bash
    # Crear el entorno virtual
    uv venv

    # Activar el entorno (en Linux/macOS)
    source .venv/bin/activate

    # Instalar dependencias, incluyendo las de desarrollo
    uv pip install -e ".[dev]"
    ```

### 3. Configuración

1.  **Crea un archivo `.env`** en el directorio `mcp-server/` copiando el ejemplo:
    ```bash
    cp .env.example .env
    ```
    *(Nota: Si `.env.example` no existe, créalo a partir de los siguientes contenidos).*

2.  **Edita el archivo `.env`** para que apunte a las URLs correctas de tus servicios y añade las API keys necesarias.

    ```dotenv
    # Endpoints de los servicios del Cognito-Stack
    OLLAMA_URL=http://localhost:11434
    QDRANT_URL=http://localhost:6333
    N8N_URL=http://localhost:5678
    COMFYUI_URL=http://localhost:8188

    # Credenciales (reemplazar con valores reales si es necesario)
    N8N_API_KEY=n8n_api_xxxxxxxxxxxxxxxxxxxxxxxx
    JWT_TOKEN=un_jwt_de_prueba_para_la_api_tarragona
    ```

### 4. Ejecución del Servidor

Para que un cliente como Claude Desktop pueda comunicarse con el servidor, ejecútalo directamente. El servidor se comunicará a través de `stdio`.

```bash
# Asegúrate de que tu entorno virtual esté activado
source .venv/bin/activate

# Ejecuta el script del servidor
python cognito_mcp_server.py
```

### 5. Ejecución de los Tests

Los tests unitarios verifican la conectividad con Ollama y Qdrant y la funcionalidad de las herramientas principales.

```bash
# Asegúrate de que tu entorno virtual esté activado
source .venv/bin/activate

# Ejecuta pytest desde el directorio mcp-server/
python -m pytest
```

---

## 🛠️ Herramientas Expuestas

- `generate_with_llm`: Genera texto usando un modelo de Ollama.
- `query_vector_db`: Realiza una búsqueda semántica en una colección de Qdrant.
- `execute_rag_pipeline`: Orquesta un flujo completo de recuperación y generación.
- `create_n8n_workflow`: (Placeholder) Crea un workflow en n8n.
- `generate_image`: (Placeholder) Genera una imagen con ComfyUI.
- `run_python_code`: (Placeholder) Ejecuta código Python en un runner de n8n.
- `query_project_data`: (Placeholder) Consulta datos de la API de Tarragona Connect.
