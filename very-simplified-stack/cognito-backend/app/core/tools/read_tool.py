import os
from typing import Any, Dict
from app.core.tools.base import AgentTool, ToolContext, ToolResult

class ReadTool(AgentTool):
    name = "read"
    description = "Read the content of a file. Supports optional offset and limit for large files."
    parameters_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file relative to cwd."},
            "offset": {"type": "integer", "description": "Character offset to start reading from.", "default": 0},
            "limit": {"type": "integer", "description": "Maximum number of characters to read.", "default": 10000},
        },
        "required": ["path"],
    }

    async def execute(self, arguments: Dict[str, Any], context: ToolContext) -> ToolResult:
        path = arguments.get("path")
        offset = arguments.get("offset", 0)
        limit = arguments.get("limit", 10000)

        if not path:
            return ToolResult(is_error=True, output="Error: path is required.")

        # Path traversal protection
        abs_cwd = os.path.realpath(context.cwd)
        target_path = os.path.realpath(os.path.join(abs_cwd, path))

        from app.core.path_safety import is_path_contained
        if not is_path_contained(target_path, abs_cwd):
            return ToolResult(is_error=True, output=f"Error: Access denied. Path '{path}' is outside of workspace.")

        if not os.path.exists(target_path):
            return ToolResult(is_error=True, output=f"Error: File '{path}' not found.")

        if os.path.isdir(target_path):
            return ToolResult(is_error=True, output=f"Error: '{path}' is a directory.")

        try:
            with open(target_path, "r", encoding="utf-8") as f:
                f.seek(offset)
                content = f.read(limit)
                return ToolResult(output=content)
        except Exception as e:
            return ToolResult(is_error=True, output=f"Error reading file: {str(e)}")
