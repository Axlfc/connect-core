import os
from pathlib import Path
from typing import Any, Dict
from app.core.tools.base import AgentTool, ToolContext, ToolResult
from app.core.fs_observation_policy import FSObservationPolicy

class EditTool(AgentTool):
    name = "edit"
    description = "DEPRECADA: Usa 'apply_unified_patch' en su lugar. Esta herramienta ya no se recomienda."
    is_read_only = False
    is_destructive = True
    concurrency_safe = False
    parameters_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file relative to cwd."},
            "old_str": {"type": "string", "description": "The exact string to be replaced."},
            "new_str": {"type": "string", "description": "The string to replace old_str with."},
        },
        "required": ["path", "old_str", "new_str"],
    }

    async def execute(self, arguments: Dict[str, Any], context: ToolContext) -> ToolResult:
        path = arguments.get("path")
        old_str = arguments.get("old_str")
        new_str = arguments.get("new_str")

        if not path or old_str is None or new_str is None:
            return ToolResult(is_error=True, output="Error: path, old_str and new_str are required.")

        policy = FSObservationPolicy(
            cwd=context.cwd,
            protected_files=getattr(context, "protected_files", None),
        )

        target_path = Path(context.cwd) / path

        if policy.is_path_ignored(target_path):
            return ToolResult(is_error=True, output=policy.get_generic_error_message())

        resolved_target = target_path.resolve()

        # Trust check
        if not context.trusted:
            return ToolResult(is_error=True, output="Proyecto no confiado (untrusted). Ejecuta project-trust set antes de escribir.")

        if not resolved_target.exists():
            return ToolResult(is_error=True, output=policy.get_generic_error_message())

        try:
            with open(resolved_target, "r", encoding="utf-8") as f:
                content = f.read()

            count = content.count(old_str)
            norm_path = os.path.normpath(path)
            if count == 0:
                return ToolResult(is_error=True, output=f"Error: old_str not found in '{norm_path}'.")
            if count > 1:
                return ToolResult(is_error=True, output=f"Error: old_str appears {count} times in '{norm_path}'. Must be unique.")

            new_content = content.replace(old_str, new_str)
            with open(resolved_target, "w", encoding="utf-8") as f:
                f.write(new_content)

            return ToolResult(output=f"File '{norm_path}' edited successfully.")
        except Exception:
            return ToolResult(is_error=True, output=policy.get_generic_error_message())
