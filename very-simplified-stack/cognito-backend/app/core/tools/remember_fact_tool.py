import logging
from typing import Dict, Any, Optional
from app.core.tools.base import AgentTool, ToolContext, ToolResult
from app.core.fact_memory import fact_memory_manager

logger = logging.getLogger("cognito.backend.tools.remember_fact")

class RememberFactTool(AgentTool):
    """
    Tool giving the agent explicit memory persistence capabilities for remembering facts,
    style preferences, or project rules across sessions (AUD-014).
    """
    name = "remember_fact"
    description = (
        "Records a permanent fact, style rule, or project knowledge detail to remember for future sessions "
        "of this user or project. Use this when the user asks you to remember a preference or rule."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "fact": {
                "type": "string",
                "description": "The specific fact, rule, or preference to remember permanently."
            },
            "category": {
                "type": "string",
                "description": "Optional category (e.g., 'estilo', 'preferencia', 'proyecto', 'regla'). Defaults to 'general'."
            },
            "user_id": {
                "type": "string",
                "description": "Optional explicit user identifier to associate the fact with."
            },
            "project_id": {
                "type": "string",
                "description": "Optional explicit project identifier to associate the fact with."
            }
        },
        "required": ["fact"]
    }

    # Behavioral risk metadata (AUD-005)
    is_read_only = False
    is_destructive = False
    concurrency_safe = True

    async def execute(self, arguments: Dict[str, Any], context: ToolContext) -> ToolResult:
        fact_text = arguments.get("fact", "").strip()
        category = arguments.get("category", "general").strip() or "general"
        user_id = arguments.get("user_id")
        project_id = arguments.get("project_id")

        if not fact_text:
            return ToolResult(is_error=True, output="Error: Fact text cannot be empty.")

        try:
            saved_fact = fact_memory_manager.save_fact(
                fact_text=fact_text,
                category=category,
                user_id=user_id,
                project_id=project_id
            )
            return ToolResult(
                is_error=False,
                output=f"Hecho recordado con éxito [ID: {saved_fact.fact_id}, Categoría: {saved_fact.category}]: '{saved_fact.fact_text}'"
            )
        except Exception as e:
            logger.error(f"Error executing RememberFactTool: {e}")
            return ToolResult(is_error=True, output=f"Error al guardar el hecho en memoria: {str(e)}")
