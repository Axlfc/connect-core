import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("cognito.backend.mcp")

class CognitoMCPServer:
    """
    Cognito Model Context Protocol (MCP) Server.
    Provides safe, non-recursive tools for Codex and external clients.
    """
    def __init__(self, max_execution_depth: int = 3):
        self.max_execution_depth = max_execution_depth
        self.enabled = True

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

        # Safe tools dispatch
        try:
            if name == "cognito_repository_search":
                return await self.cognito_repository_search(arguments)
            elif name == "cognito_architecture_context":
                return await self.cognito_architecture_context(arguments)
            elif name == "cognito_known_failures":
                return await self.cognito_known_failures(arguments)
            elif name == "cognito_task_status":
                return await self.cognito_task_status(arguments)
            elif name == "cognito_model_catalog":
                return await self.cognito_model_catalog()
            elif name == "cognito_worker_health":
                return await self.cognito_worker_health()
            elif name == "cognito_verification_results":
                return await self.cognito_verification_results(arguments)
            else:
                return {"is_error": True, "output": f"Unknown tool: {name}"}
        except Exception as e:
            logger.error(f"Error executing MCP tool {name}: {e}")
            return {"is_error": True, "output": f"Execution error: {str(e)}"}

    async def cognito_repository_search(self, args: Dict[str, Any]) -> Dict[str, Any]:
        query = args.get("query", "")
        # Query semantic memory (Qdrant)
        from app.services.qdrant_memory import qdrant_memory
        results = await qdrant_memory.search_points("cognito_repository_context", [0.1] * 128, limit=3)
        return {"results": results}

    async def cognito_architecture_context(self, args: Dict[str, Any]) -> Dict[str, Any]:
        # Simple architecture summary
        return {
            "architecture": "Cognito-Codex Router Stack: control-plane, host worker, VS Code extension.",
            "components": ["cognito-backend", "cognito-worker", "vscode-cognito-router"]
        }

    async def cognito_known_failures(self, args: Dict[str, Any]) -> Dict[str, Any]:
        from app.services.qdrant_memory import qdrant_memory
        results = await qdrant_memory.search_points("cognito_known_failures", [0.1] * 128, limit=3)
        return {"failures": results}

    async def cognito_task_status(self, args: Dict[str, Any]) -> Dict[str, Any]:
        task_id = args.get("task_id", "")
        from app.services.task_store import task_store
        task = await task_store.get_task(task_id)
        if not task:
            return {"status": "not_found"}
        return {"task_id": task.task_id, "status": task.status}

    async def cognito_model_catalog(self) -> Dict[str, Any]:
        from app.services.model_discovery import model_discovery_service
        catalog = await model_discovery_service.get_combined_catalog()
        return {"catalog": catalog}

    async def cognito_worker_health(self) -> Dict[str, Any]:
        from app.services.worker_client import worker_client
        health = await worker_client.get_health()
        return {"health": health}

    async def cognito_verification_results(self, args: Dict[str, Any]) -> Dict[str, Any]:
        task_id = args.get("task_id", "")
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

mcp_server = CognitoMCPServer()
