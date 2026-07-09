import os
from typing import Any, Dict
from app.core.tools.base import AgentTool, ToolContext, ToolResult

class WriteTool(AgentTool):
    name = "write"
    description = "Write or overwrite a file with the provided content."
    parameters_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file relative to cwd."},
            "content": {"type": "string", "description": "Content to write to the file."},
        },
        "required": ["path", "content"],
    }

    async def execute(self, arguments: Dict[str, Any], context: ToolContext) -> ToolResult:
        path = arguments.get("path")
        content = arguments.get("content")

        if not path or content is None:
            return ToolResult(is_error=True, output="Error: path and content are required.")

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

        try:
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(content)
            return ToolResult(output=f"File '{norm_path}' written successfully.")
        except Exception as e:
            return ToolResult(is_error=True, output=f"Error writing file: {str(e)}")
