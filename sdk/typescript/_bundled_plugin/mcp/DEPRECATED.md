# Deprecation & Migration Guide

## Status: Deprecated

The bundled JavaScript MCP server implementation located in `sdk/typescript/_bundled_plugin/mcp/server.mjs` has been deprecated and unified into the canonical Python MCP server.

## Canonical MCP Server Location

The single canonical MCP server implementation for Cognito is now located at:

```
very-simplified-stack/cognito-backend/app/services/mcp_server.py
```

## Migration Instructions

1. **Service Execution**:
   Run the canonical MCP server using Python and FastMCP:
   ```bash
   cd very-simplified-stack/cognito-backend
   PYTHONPATH=. python3 app/services/mcp_server.py
   ```

2. **Configuration & Authentication**:
   The canonical MCP server uses layered configuration loaded automatically from:
   - Default values
   - `~/.cognito/config.json`
   - Environment variables (`COGNITO_AUTH_TOKEN`, `COGNITO_API_KEY`, `COGNITO_ENDPOINT`)

3. **Exposed Canonical Tools**:
   - `execute_agent_task`: Submit prompts and receive agent results or SSE event streams.
   - `get_session_status`: Retrieve session status and task summaries.
   - `cognito_repository_search`, `cognito_architecture_context`, `cognito_known_failures`, `cognito_task_status`, `cognito_model_catalog`, `cognito_worker_health`, `cognito_verification_results`, `generate_with_llm`, `query_vector_db`, `execute_rag_pipeline`.
