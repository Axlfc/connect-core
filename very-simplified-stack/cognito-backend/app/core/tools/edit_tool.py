import os
from typing import Any, Dict
from app.core.tools.base import AgentTool, ToolContext, ToolResult

class EditTool(AgentTool):
    name = "edit"
    description = "Edit a file by replacing a specific string with a new one."
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

        abs_cwd = os.path.realpath(context.cwd)
        norm_path = os.path.normpath(path)
        target_path = os.path.realpath(os.path.join(abs_cwd, norm_path))

        # Path traversal protection
        if not target_path.startswith(abs_cwd):
            return ToolResult(is_error=True, output=f"Error: Access denied. Path '{path}' is outside of workspace.")

        # Protected files check
        if norm_path in context.protected_files:
            return ToolResult(is_error=True, output=f"Archivo protegido: {norm_path}. No se puede modificar vía agente.")

        # Trust check
        if not context.trusted:
            return ToolResult(is_error=True, output="Proyecto no confiado (untrusted). Ejecuta project-trust set antes de escribir.")

        if not os.path.exists(target_path):
            return ToolResult(is_error=True, output=f"Error: File '{path}' not found.")

        try:
            with open(target_path, "r", encoding="utf-8") as f:
                content = f.read()

            count = content.count(old_str)
            if count == 0:
                return ToolResult(is_error=True, output=f"Error: old_str not found in '{path}'.")
            if count > 1:
                return ToolResult(is_error=True, output=f"Error: old_str appears {count} times in '{path}'. Must be unique.")

            new_content = content.replace(old_str, new_str)
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            return ToolResult(output=f"File '{norm_path}' edited successfully.")
        except Exception as e:
            return ToolResult(is_error=True, output=f"Error editing file: {str(e)}")
