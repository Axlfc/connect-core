import os
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
        path = arguments.get("path")
        offset = arguments.get("offset", 0)
        limit = arguments.get("limit", 10000)

        if not path:
            return ToolResult(is_error=True, output="Error: path is required.")

        policy = FSObservationPolicy(
            cwd=context.cwd,
            protected_files=getattr(context, "protected_files", None),
        )

        target_path = Path(context.cwd) / path

        # Check observation policy and path safety
        if policy.is_path_ignored(target_path):
            return ToolResult(is_error=True, output=policy.get_generic_error_message())

        resolved_target = target_path.resolve()

        if not resolved_target.exists():
            return ToolResult(is_error=True, output=policy.get_generic_error_message())

        if resolved_target.is_dir():
            return ToolResult(is_error=True, output=policy.get_generic_error_message())

        try:
            with open(resolved_target, "r", encoding="utf-8") as f:
                f.seek(offset)
                content = f.read(limit)
                return ToolResult(output=content)
        except Exception:
            return ToolResult(is_error=True, output=policy.get_generic_error_message())
