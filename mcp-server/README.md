# Servidor MCP de Herramientas del Cognito-Stack (Consolidado)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/mcp-server/README.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/mcp-server/README.en.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/mcp-server/README.ca.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/mcp-server/README.zh-cn.md)

> ⚠️ **Aviso de Migración y Consolidación**: La implementación de servidor MCP ha sido unificada en la ubicación canónica:
> **`very-simplified-stack/cognito-backend/app/services/mcp_server.py`**.

Este directorio se mantiene para compatibilidad y delega la ejecución de herramientas a la implementación canónica en `cognito-backend`.

## 🚀 Ubicación Canónica y Ejecución

Para ejecutar el servidor MCP canónico:

```bash
cd very-simplified-stack/cognito-backend
PYTHONPATH=. python3 app/services/mcp_server.py
```

### Autenticación y Configuración en Capas (`~/.cognito/config.json`)

El servidor MCP canónico admite autenticación y configuración jerárquica:
1. Valores por defecto
2. `~/.cognito/config.json`
3. Variables de entorno (`COGNITO_AUTH_TOKEN`, `COGNITO_API_KEY`, `COGNITO_ENDPOINT`)

## 🛠️ Herramientas Canónicas Principales

- `execute_agent_task`: Permite a un cliente externo enviar un prompt y recibir eventos SSE o un resultado final.
- `get_session_status`: Devuelve metadatos, historial y estado de una sesión.
- `cognito_repository_search`, `cognito_architecture_context`, `cognito_known_failures`, `cognito_task_status`, `cognito_model_catalog`, `cognito_worker_health`, `cognito_verification_results`.
- `generate_with_llm`, `query_vector_db`, `execute_rag_pipeline`.
