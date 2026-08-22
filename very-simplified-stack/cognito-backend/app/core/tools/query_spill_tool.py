from typing import Any, Dict, List, Optional
from app.core.tools.base import AgentTool, ToolContext, ToolResult
from app.core.context_spill import default_spill_manager, SpillManager

class QuerySpillTool(AgentTool):
    name = "query_spill"
    description = (
        "Query content from external spill memory using a spill_id. "
        "Allows searching for specific terms/keywords or retrieving specific line ranges."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "spill_id": {
                "type": "string",
                "description": "The unique identifier of the spilled content (e.g. spill_abc123)."
            },
            "query": {
                "type": "string",
                "description": "Optional search term or keyword to filter matching lines."
            },
            "line_range": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "Optional 2-element array [start_line, end_line] (1-indexed) specifying lines to retrieve.",
                "minItems": 2,
                "maxItems": 2
            }
        },
        "required": ["spill_id"]
    }

    def __init__(self, spill_manager: Optional[SpillManager] = None):
        self.spill_manager = spill_manager or default_spill_manager

    async def execute(self, arguments: Dict[str, Any], context: ToolContext) -> ToolResult:
        spill_id = arguments.get("spill_id")
        query = arguments.get("query")
        line_range = arguments.get("line_range")

        if not spill_id:
            return ToolResult(is_error=True, output="Error: spill_id is required.")

        result = self.spill_manager.query_spill(
            spill_id=spill_id,
            query=query,
            line_range=line_range
        )

        if result.startswith("Error:"):
            return ToolResult(is_error=True, output=result)

        return ToolResult(output=result)
