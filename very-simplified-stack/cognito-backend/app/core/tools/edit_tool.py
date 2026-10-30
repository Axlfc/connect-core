import os
import tempfile
from pathlib import Path
from typing import Any, Dict
from app.core.tools.base import AgentTool, ToolContext, ToolResult
from app.core.fs_observation_policy import FSObservationPolicy
from app.core.path_safety import resolve_in_workspace


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

        resolved_target = resolve_in_workspace(path, context.cwd)
        if resolved_target is None:
            return ToolResult(is_error=True, output=policy.get_generic_error_message())

        target_path = Path(context.cwd) / path

        if policy.is_path_ignored(target_path) or policy.is_path_ignored(resolved_target):
            return ToolResult(is_error=True, output=policy.get_generic_error_message())

        # Trust check
        if not context.trusted:
            return ToolResult(is_error=True, output="Proyecto no confiado (untrusted). Ejecuta project-trust set antes de escribir.")

        if not resolved_target.exists() or resolved_target.is_dir():
            return ToolResult(is_error=True, output=policy.get_generic_error_message())

        target_dir = resolved_target.parent
        temp_path = None
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

            # Atomic write via temporary file in the same directory
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target_dir, delete=False) as temp_file:
                temp_path = temp_file.name
                temp_file.write(new_content)
                temp_file.flush()
                os.fsync(temp_file.fileno())

            os.replace(temp_path, str(resolved_target))
            return ToolResult(output=f"File '{norm_path}' edited successfully.")
        except Exception as e:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            return ToolResult(is_error=True, output=f"Error editing file: {str(e)}")
