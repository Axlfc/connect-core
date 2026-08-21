from pathlib import Path
from typing import Any, Dict
from app.core.tools.base import AgentTool, ToolContext, ToolResult
from app.core.fs_observation_policy import FSObservationPolicy

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
        path_str = arguments.get("path")
        offset = arguments.get("offset", 0)
        limit = arguments.get("limit", 10000)

        if not path_str:
            return ToolResult(is_error=True, output="Error: path is required.")

        GENERIC_ERROR = "Archivo o directorio no encontrado o no accesible"

        cwd_path = Path(context.cwd).resolve()
        policy = FSObservationPolicy(
            cwd=cwd_path,
            protected_files=getattr(context, "protected_files", None)
        )

        if policy.is_hidden(path_str):
            return ToolResult(is_error=True, output=GENERIC_ERROR)

        try:
            target_path = (cwd_path / Path(path_str)).resolve()
        except Exception:
            return ToolResult(is_error=True, output=GENERIC_ERROR)

        if not target_path.exists() or target_path.is_dir():
            return ToolResult(is_error=True, output=GENERIC_ERROR)

        try:
            with target_path.open("r", encoding="utf-8") as f:
                f.seek(offset)
                content = f.read(limit)
                return ToolResult(output=content)
        except Exception as e:
            return ToolResult(is_error=True, output=f"Error reading file: {str(e)}")
