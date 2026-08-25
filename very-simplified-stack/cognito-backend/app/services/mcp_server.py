import os
import json
import logging
import secrets
import httpx
from pathlib import Path
from typing import Dict, Any, List, Optional

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    from mcp.server.mcpserver import MCPServer as FastMCP

logger = logging.getLogger("cognito.backend.mcp")

def load_mcp_config() -> Dict[str, Any]:
    """
    Loads hierarchically resolved configuration for the Cognito MCP server.
    Layered resolution: Defaults -> ~/.cognito/config.json -> Environment Variables.
    """
    insecure_dev = os.getenv("COGNITO_MCP_INSECURE_DEV", "false").lower() in ("true", "1", "yes")
    if insecure_dev:
        logger.warning("WARNING: MCP Server running in INSECURE DEV MODE. Authentication is disabled!")
        require_auth = False
    else:
        require_auth = True

    config = {
        "Endpoint": os.getenv("COGNITO_ENDPOINT", "http://localhost:8000"),
        "AuthToken": os.getenv("COGNITO_AUTH_TOKEN", ""),
        "APIKey": os.getenv("COGNITO_API_KEY", ""),
        "MaxExecutionDepth": int(os.getenv("COGNITO_MCP_MAX_DEPTH", "3")),
        "RequireAuth": require_auth,
        "InsecureDev": insecure_dev,
        "OllamaURL": os.getenv("OLLAMA_URL", "http://localhost:11434"),
        "QdrantURL": os.getenv("QDRANT_URL", "http://localhost:6333"),
        "N8nURL": os.getenv("N8N_URL", "http://localhost:5678"),
        "ComfyUIURL": os.getenv("COMFYUI_URL", "http://localhost:8188"),
    }

    config_path = Path.home() / ".cognito" / "config.json"
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                file_config = json.load(f)
                for k, v in file_config.items():
                    if k in config and k != "RequireAuth":
                        config[k] = v
                    elif k.lower() in ("auth_token", "authtoken"):
                        config["AuthToken"] = v
                    elif k.lower() in ("api_key", "apikey"):
                        config["APIKey"] = v
        except Exception as e:
            logger.warning(f"Could not load ~/.cognito/config.json: {e}")

    # Environment variables overrides (highest precedence)
    if os.getenv("COGNITO_ENDPOINT"):
        config["Endpoint"] = os.getenv("COGNITO_ENDPOINT")
    if os.getenv("COGNITO_AUTH_TOKEN"):
        config["AuthToken"] = os.getenv("COGNITO_AUTH_TOKEN")
    if os.getenv("COGNITO_API_KEY"):
        config["APIKey"] = os.getenv("COGNITO_API_KEY")

    # Generate random token if none is provided, persist it, and log/communicate it
    if not config["AuthToken"] and not config["APIKey"]:
        generated_token = secrets.token_urlsafe(32)
        config["AuthToken"] = generated_token
        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.chmod(config_path.parent, 0o700)
            except Exception:
                pass
            file_data = {}
            if config_path.exists():
                try:
                    with open(config_path, "r", encoding="utf-8") as f:
                        file_data = json.load(f)
                except Exception:
                    file_data = {}
            file_data["AuthToken"] = generated_token
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(file_data, f, indent=2)
            try:
                os.chmod(config_path, 0o600)
            except Exception:
                pass
            logger.warning(
                f"No auth token configured. Generated ephemeral AuthToken '{generated_token}' and persisted to {config_path}"
            )
        except Exception as e:
            logger.error(f"Could not persist generated AuthToken to {config_path}: {e}")
            raise RuntimeError(f"Failed to persist generated AuthToken to {config_path}: {e}") from e

    return config

def verify_mcp_auth(auth_token: Optional[str] = None) -> bool:
    """
    Verifies authentication against layered configuration.
    Fail-closed by default: requires valid non-empty authentication token matching expected token.
    """
    config = load_mcp_config()
    require_auth = config.get("RequireAuth", True)

    if not require_auth:
        return True

    expected_token = config.get("AuthToken") or config.get("APIKey")
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
        Call a safe MCP tool with recursion protection.
        """
        if not self.validate_recursion(origin, correlation_id, execution_depth):
            return {
                "is_error": True,
                "output": f"Error: Recursive execution depth limit exceeded ({execution_depth} > {self.max_execution_depth})."
            }

        try:
            if name == "execute_agent_task":
                return await execute_agent_task(**arguments)
            elif name == "get_session_status":
                return await get_session_status(**arguments)
            elif name == "cognito_repository_search":
                return await cognito_repository_search(**arguments)
            elif name == "cognito_architecture_context":
                return await cognito_architecture_context()
            elif name == "cognito_known_failures":
                return await cognito_known_failures(**arguments)
            elif name == "cognito_task_status":
                return await cognito_task_status(**arguments)
            elif name == "cognito_model_catalog":
                return await cognito_model_catalog()
            elif name == "cognito_worker_health":
                return await cognito_worker_health()
            elif name == "cognito_verification_results":
                return await cognito_verification_results(**arguments)
            elif name == "generate_with_llm":
                res = await generate_with_llm(**arguments)
                return {"result": res}
            elif name == "query_vector_db":
                res = await query_vector_db(**arguments)
                return {"result": res}
            elif name == "execute_rag_pipeline":
                res = await execute_rag_pipeline(**arguments)
                return {"result": res}
            else:
                return {"is_error": True, "output": f"Unknown tool: {name}"}
        except Exception as e:
            logger.error(f"Error executing MCP tool {name}: {e}")
            return {"is_error": True, "output": f"Execution error: {str(e)}"}

mcp_server = CognitoMCPServer()

def main():
    if hasattr(mcp, "run"):
        mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
