import os
import json
import logging
import secrets
import httpx
import jsonschema
from pathlib import Path
from typing import Dict, Any, List, Optional
from app.core.tools.base import format_validation_error
from app.core.secrets import get_secrets_provider

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    from mcp.server.mcpserver import MCPServer as FastMCP

logger = logging.getLogger("cognito.backend.mcp")

MCP_TOOL_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "execute_agent_task": {
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "El prompt o instrucción para el agente."},
                "cwd": {"type": "string", "description": "Directorio de trabajo.", "default": "."},
                "session_id": {"type": ["string", "null"], "description": "ID opcional de sesión."},
                "stream": {"type": "boolean", "description": "Si responder con SSE streaming.", "default": False},
                "auth_token": {"type": ["string", "null"], "description": "Token de autenticación opcional."},
            },
            "required": ["prompt"],
        },
        "return": {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "session_id": {"type": "string"},
                "response": {"type": "string"},
                "is_error": {"type": "boolean"},
                "output": {"type": "string"},
            },
        },
    },
    "get_session_status": {
        "parameters": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "ID de la sesión a consultar."},
                "auth_token": {"type": ["string", "null"], "description": "Token de autenticación opcional."},
            },
            "required": ["session_id"],
        },
        "return": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "status": {"type": "string"},
                "is_error": {"type": "boolean"},
                "output": {"type": "string"},
            },
        },
    },
    "cognito_repository_search": {
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Consulta de búsqueda.", "default": ""},
            },
        },
        "return": {
            "type": "object",
            "properties": {
                "results": {"type": "array"},
                "is_error": {"type": "boolean"},
                "output": {"type": "string"},
            },
        },
    },
    "cognito_architecture_context": {
        "parameters": {
            "type": "object",
            "properties": {},
        },
        "return": {
            "type": "object",
            "properties": {
                "architecture": {"type": "string"},
                "components": {"type": "array"},
            },
        },
    },
    "cognito_known_failures": {
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Consulta de búsqueda.", "default": ""},
            },
        },
        "return": {
            "type": "object",
            "properties": {
                "failures": {"type": "array"},
                "is_error": {"type": "boolean"},
                "output": {"type": "string"},
            },
        },
    },
    "cognito_task_status": {
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "ID de la tarea.", "default": ""},
            },
        },
        "return": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "status": {"type": "string"},
                "is_error": {"type": "boolean"},
                "output": {"type": "string"},
            },
        },
    },
    "cognito_model_catalog": {
        "parameters": {
            "type": "object",
            "properties": {},
        },
        "return": {
            "type": "object",
            "properties": {
                "catalog": {"type": ["object", "array"]},
                "is_error": {"type": "boolean"},
                "output": {"type": "string"},
            },
        },
    },
    "cognito_worker_health": {
        "parameters": {
            "type": "object",
            "properties": {},
        },
        "return": {
            "type": "object",
            "properties": {
                "health": {"type": "object"},
                "is_error": {"type": "boolean"},
                "output": {"type": "string"},
            },
        },
    },
    "cognito_verification_results": {
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "ID de la tarea.", "default": ""},
            },
        },
        "return": {
            "type": "object",
            "properties": {
                "verification_runs": {"type": "array"},
                "is_error": {"type": "boolean"},
                "output": {"type": "string"},
            },
        },
    },
    "generate_with_llm": {
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Prompt para la generación."},
                "model": {"type": "string", "default": "llama3.2"},
                "system_prompt": {"type": "string", "default": ""},
            },
            "required": ["prompt"],
        },
        "return": {
            "type": "object",
            "properties": {
                "result": {"type": "string"},
                "is_error": {"type": "boolean"},
                "output": {"type": "string"},
            },
        },
    },
    "query_vector_db": {
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Consulta de vectores."},
                "collection": {"type": "string", "default": "documents"},
            },
            "required": ["query"],
        },
        "return": {
            "type": "object",
            "properties": {
                "result": {"type": "string"},
                "is_error": {"type": "boolean"},
                "output": {"type": "string"},
            },
        },
    },
    "execute_rag_pipeline": {
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Consulta para RAG."},
                "project_id": {"type": ["string", "null"]},
            },
            "required": ["query"],
        },
        "return": {
            "type": "object",
            "properties": {
                "result": {"type": "string"},
                "is_error": {"type": "boolean"},
                "output": {"type": "string"},
            },
        },
    },
}


def validate_mcp_input(tool_name: str, arguments: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Validates MCP tool input arguments fail-fast against its parameters schema.
    Returns error dict if invalid, or None if valid.
    """
    schema_info = MCP_TOOL_SCHEMAS.get(tool_name)
    if not schema_info:
        return None
    param_schema = schema_info.get("parameters")
    if not param_schema:
        return None

    if not isinstance(arguments, dict):
        arguments = {}

    try:
        jsonschema.validate(instance=arguments, schema=param_schema)
        return None
    except jsonschema.exceptions.ValidationError as ve:
        err_msg = format_validation_error(
            tool_name=tool_name,
            schema=param_schema,
            arguments=arguments,
            error=ve,
        )
        return {"is_error": True, "output": err_msg}


def validate_mcp_output(tool_name: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validates MCP tool return value against its return schema.
    Returns structured error dict if invalid, or original result if valid.
    """
    schema_info = MCP_TOOL_SCHEMAS.get(tool_name)
    if not schema_info:
        return result
    ret_schema = schema_info.get("return")
    if not ret_schema or not isinstance(result, dict) or result.get("is_error"):
        return result

    try:
        jsonschema.validate(instance=result, schema=ret_schema)
        return result
    except jsonschema.exceptions.ValidationError as ve:
        err_msg = f"Error de validación en el tipo de retorno de '{tool_name}': {ve.message}"
        return {"is_error": True, "output": err_msg}

def load_mcp_config() -> Dict[str, Any]:
    """
    Loads hierarchically resolved configuration for the Cognito MCP server.
    Layered resolution: Defaults -> SecretsProvider -> Environment Variables.
    """
    insecure_dev = os.getenv("COGNITO_MCP_INSECURE_DEV", "false").lower() in ("true", "1", "yes")
    if insecure_dev:
        logger.warning("WARNING: MCP Server running in INSECURE DEV MODE. Authentication is disabled!")
        require_auth = False
    else:
        require_auth = True

    provider = get_secrets_provider()
    auth_token = provider.get_secret("AuthToken") or ""
    api_key = provider.get_secret("APIKey") or ""

    config = {
        "Endpoint": os.getenv("COGNITO_ENDPOINT", "http://localhost:8000"),
        "AuthToken": auth_token,
        "APIKey": api_key,
        "MaxExecutionDepth": int(os.getenv("COGNITO_MCP_MAX_DEPTH", "3")),
        "RequireAuth": require_auth,
        "InsecureDev": insecure_dev,
        "OllamaURL": os.getenv("OLLAMA_URL", "http://localhost:11434"),
        "QdrantURL": os.getenv("QDRANT_URL", "http://localhost:6333"),
        "N8nURL": os.getenv("N8N_URL", "http://localhost:5678"),
        "ComfyUIURL": os.getenv("COMFYUI_URL", "http://localhost:8188"),
    }

    # Environment variables overrides (highest precedence)
    if os.getenv("COGNITO_ENDPOINT"):
        config["Endpoint"] = os.getenv("COGNITO_ENDPOINT")

    return config

def verify_mcp_auth(auth_token: Optional[str] = None) -> bool:
    """
    Verifies authentication against SecretsProvider abstraction.
    Fail-closed by default: requires valid non-empty authentication token matching expected token.
    """
    insecure_dev = os.getenv("COGNITO_MCP_INSECURE_DEV", "false").lower() in ("true", "1", "yes")
    if insecure_dev:
        return True

    provider = get_secrets_provider()
    expected_token = provider.get_secret("AuthToken") or provider.get_secret("APIKey")
    if not expected_token:
        logger.warning("MCP authentication failed: no expected auth token configured.")
        return False

    if not auth_token:
        auth_token = os.getenv("COGNITO_AUTH_TOKEN") or os.getenv("COGNITO_API_KEY")

    if not auth_token or auth_token != expected_token:
        logger.warning("MCP authentication failed: invalid or missing auth token.")
        return False

    return True

# Initialize canonical FastMCP server
mcp = FastMCP("cognito-mcp-server")

@mcp.tool()
async def execute_agent_task(
    prompt: str,
    cwd: str = ".",
    session_id: Optional[str] = None,
    stream: bool = False,
    auth_token: Optional[str] = None
) -> Dict[str, Any]:
    """
    Permite a un cliente externo (ej. IDE) enviar un prompt y recibir eventos SSE o un resultado final.

    Args:
        prompt: El prompt o instrucción para el agente.
        cwd: Directorio de trabajo para el agente.
        session_id: ID opcional de la sesión existente.
        stream: Si es True, indica que se responderá mediante streaming SSE.
        auth_token: Token de autenticación opcional.
    """
    if not verify_mcp_auth(auth_token):
        return {"is_error": True, "output": "Authentication failed. Invalid auth_token."}

    try:
        from app.core.session_manager import SessionManager
        session_mgr = SessionManager()

        if session_id == "latest":
            resolved_session_id = session_mgr.continue_recent(cwd) or session_mgr.create(cwd)
        elif session_id:
            resolved_session_id = session_id
        else:
            resolved_session_id = session_mgr.create(cwd)

        session_mgr.append_message(resolved_session_id, "user", prompt)

        if stream:
            return {
                "status": "streaming",
                "session_id": resolved_session_id,
                "sse_endpoint": f"/api/agent/loop",
                "prompt": prompt
            }

        # Non-streaming execution summary
        from app.services.reasoning_engine import reasoning_engine
        from app.models.ai import AIRequest

        ai_req = AIRequest(prompt=prompt, session_id=resolved_session_id)
        ai_resp = await reasoning_engine.process_request(ai_req)

        session_mgr.append_message(resolved_session_id, "assistant", ai_resp.response)

        return {
            "status": "completed",
            "session_id": resolved_session_id,
            "response": ai_resp.response,
            "metadata": ai_resp.metadata
        }
    except Exception as e:
        logger.error(f"Error executing agent task: {e}")
        return {"is_error": True, "output": f"Task execution failed: {str(e)}"}

@mcp.tool()
async def get_session_status(
    session_id: str,
    auth_token: Optional[str] = None
) -> Dict[str, Any]:
    """
    Devuelve el estado y metadatos de una sesión.

    Args:
        session_id: ID de la sesión a consultar.
        auth_token: Token de autenticación opcional.
    """
    if not verify_mcp_auth(auth_token):
        return {"is_error": True, "output": "Authentication failed. Invalid auth_token."}

    try:
        from app.core.session_manager import SessionManager
        session_mgr = SessionManager()
        metadata = session_mgr.open(session_id)
        messages = session_mgr.get_effective_messages(session_id)

        from app.services.task_store import task_store
        tasks = await task_store.list_tasks(session_id=session_id)
        task_summary = [{"task_id": t.task_id, "status": t.status, "title": t.title} for t in tasks]

        return {
            "session_id": metadata.session_id,
            "cwd": metadata.cwd,
            "created_at": metadata.created_at,
            "updated_at": metadata.updated_at,
            "message_count": metadata.message_count,
            "effective_message_count": len(messages),
            "tasks": task_summary,
            "status": "active"
        }
    except FileNotFoundError:
        return {"is_error": True, "output": f"Session '{session_id}' not found."}
    except Exception as e:
        logger.error(f"Error getting session status: {e}")
        return {"is_error": True, "output": f"Error retrieving session status: {str(e)}"}

@mcp.tool()
async def cognito_repository_search(query: str = "") -> Dict[str, Any]:
    """Busca contexto de código en la memoria vectorial (Qdrant)."""
    try:
        from app.services.qdrant_memory import qdrant_memory
        results = await qdrant_memory.search_points("cognito_repository_context", [0.1] * 128, limit=3)
        return {"results": results}
    except Exception as e:
        return {"is_error": True, "output": str(e)}

@mcp.tool()
async def cognito_architecture_context() -> Dict[str, Any]:
    """Devuelve la arquitectura general del sistema Cognito."""
    return {
        "architecture": "Cognito-Codex Router Stack: control-plane, host worker, VS Code extension.",
        "components": ["cognito-backend", "cognito-worker", "vscode-cognito-router"]
    }

@mcp.tool()
async def cognito_known_failures(query: str = "") -> Dict[str, Any]:
    """Busca fallos conocidos o post-mortems indexados."""
    try:
        from app.services.qdrant_memory import qdrant_memory
        results = await qdrant_memory.search_points("cognito_known_failures", [0.1] * 128, limit=3)
        return {"failures": results}
    except Exception as e:
        return {"is_error": True, "output": str(e)}

@mcp.tool()
async def cognito_task_status(task_id: str = "") -> Dict[str, Any]:
    """Obtiene el estado de una tarea por su task_id."""
    try:
        from app.services.task_store import task_store
        task = await task_store.get_task(task_id)
        if not task:
            return {"status": "not_found"}
        return {"task_id": task.task_id, "status": task.status}
    except Exception as e:
        return {"is_error": True, "output": str(e)}

@mcp.tool()
async def cognito_model_catalog() -> Dict[str, Any]:
    """Devuelve el catálogo combinado de modelos disponibles."""
    try:
        from app.services.model_discovery import model_discovery_service
        catalog = await model_discovery_service.get_combined_catalog()
        return {"catalog": catalog}
    except Exception as e:
        return {"is_error": True, "output": str(e)}

@mcp.tool()
async def cognito_worker_health() -> Dict[str, Any]:
    """Verifica el estado de salud de los workers conectados."""
    try:
        from app.services.worker_client import worker_client
        health = await worker_client.get_health()
        return {"health": health}
    except Exception as e:
        return {"is_error": True, "output": str(e)}

@mcp.tool()
async def cognito_verification_results(task_id: str = "") -> Dict[str, Any]:
    """Obtiene los resultados de verificación de ejecuciones pasadas para una tarea."""
    try:
        from app.services.task_store import task_store
        attempts = await task_store.get_attempts(task_id)
        results = []
        for att in attempts:
            if att.verification:
                results.append({
                    "attempt": att.attempt_number,
                    "exit_status": att.verification.exit_status,
                    "failed_tests": att.verification.failed_tests,
                    "failure_classification": att.verification.failure_classification
                })
        return {"verification_runs": results}
    except Exception as e:
        return {"is_error": True, "output": str(e)}

@mcp.tool()
async def generate_with_llm(prompt: str, model: str = "llama3.2", system_prompt: str = "") -> str:
    """Genera texto usando la API de Ollama."""
    config = load_mcp_config()
    ollama_url = config.get("OllamaURL", "http://localhost:11434")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{ollama_url}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "system": system_prompt,
                "stream": False
            },
            timeout=60.0
        )
        response.raise_for_status()
        return response.json()["response"]

@mcp.tool()
async def query_vector_db(query: str, collection: str = "documents") -> str:
    """Busca puntos vectoriales en Qdrant."""
    config = load_mcp_config()
    ollama_url = config.get("OllamaURL", "http://localhost:11434")
    qdrant_url = config.get("QdrantURL", "http://localhost:6333")

    async with httpx.AsyncClient() as client:
        embedding_response = await client.post(
            f"{ollama_url}/api/embeddings",
            json={"model": "nomic-embed-text", "prompt": query},
            timeout=30.0
        )
        embedding_response.raise_for_status()
        embedding = embedding_response.json()["embedding"]

        qdrant_response = await client.post(
            f"{qdrant_url}/collections/{collection}/points/search",
            json={
                "vector": embedding,
                "limit": 5,
                "with_payload": True
            }
        )
        qdrant_response.raise_for_status()
        results = qdrant_response.json()["result"]
        return json.dumps(results, indent=2)

@mcp.tool()
async def execute_rag_pipeline(query: str, project_id: Optional[str] = None) -> str:
    """Pipeline RAG completo: recuperación + generación contextualizada."""
    docs_json = await query_vector_db(query, collection="documents")
    docs = json.loads(docs_json)
    context_str = "\n".join([doc.get("payload", {}).get("text", "") for doc in docs if isinstance(doc, dict)])

    full_prompt = f"Contexto relevante:\n{context_str}\n\nPregunta: {query}"
    return await generate_with_llm(
        prompt=full_prompt,
        model="llama3.2",
        system_prompt="Eres un asistente experto en Cognito OS. Cita las fuentes empleadas."
    )


class CognitoMCPServer:
    """
    Cognito Model Context Protocol (MCP) Server wrapper class.
    Maintains backward compatibility with internal backend callers and recursion controls.
    """
    def __init__(self, max_execution_depth: Optional[int] = None):
        config = load_mcp_config()
        self.max_execution_depth = max_execution_depth or config.get("MaxExecutionDepth", 3)
        self.enabled = True
        self.fastmcp = mcp

    def validate_recursion(self, origin: str, correlation_id: str, execution_depth: int) -> bool:
        """
        Validates recursion limit to prevent recursive loops.
        """
        if execution_depth > self.max_execution_depth:
            logger.warning(
                f"Recursive execution blocked: depth {execution_depth} > max limit {self.max_execution_depth} "
                f"for origin={origin} and correlation_id={correlation_id}."
            )
            return False
        return True

    async def call_tool(self, name: str, arguments: Dict[str, Any], origin: str, correlation_id: str, execution_depth: int = 1) -> Dict[str, Any]:
        """
        Call a safe MCP tool with recursion protection and strict input/output validation.
        """
        if not self.validate_recursion(origin, correlation_id, execution_depth):
            return {
                "is_error": True,
                "output": f"Error: Recursive execution depth limit exceeded ({execution_depth} > {self.max_execution_depth})."
            }

        input_err = validate_mcp_input(name, arguments)
        if input_err is not None:
            return input_err

        try:
            if name == "execute_agent_task":
                raw_res = await execute_agent_task(**arguments)
            elif name == "get_session_status":
                raw_res = await get_session_status(**arguments)
            elif name == "cognito_repository_search":
                raw_res = await cognito_repository_search(**arguments)
            elif name == "cognito_architecture_context":
                raw_res = await cognito_architecture_context()
            elif name == "cognito_known_failures":
                raw_res = await cognito_known_failures(**arguments)
            elif name == "cognito_task_status":
                raw_res = await cognito_task_status(**arguments)
            elif name == "cognito_model_catalog":
                raw_res = await cognito_model_catalog()
            elif name == "cognito_worker_health":
                raw_res = await cognito_worker_health()
            elif name == "cognito_verification_results":
                raw_res = await cognito_verification_results(**arguments)
            elif name == "generate_with_llm":
                res = await generate_with_llm(**arguments)
                raw_res = {"result": res}
            elif name == "query_vector_db":
                res = await query_vector_db(**arguments)
                raw_res = {"result": res}
            elif name == "execute_rag_pipeline":
                res = await execute_rag_pipeline(**arguments)
                raw_res = {"result": res}
            else:
                return {"is_error": True, "output": f"Unknown tool: {name}"}

            return validate_mcp_output(name, raw_res)
        except Exception as e:
            logger.error(f"Error executing MCP tool {name}: {e}")
            return {"is_error": True, "output": f"Execution error: {str(e)}"}

mcp_server = CognitoMCPServer()

def main():
    if hasattr(mcp, "run"):
        mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
