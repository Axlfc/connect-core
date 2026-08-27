import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict
from app.core.tools.base import AgentTool, ToolContext, ToolResult
from app.core.path_safety import is_path_contained

class WriteTool(AgentTool):
    name = "write"
    description = "Write or overwrite a file with the provided content."
    is_read_only = False
    is_destructive = True
    concurrency_safe = False
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
        if not is_path_contained(target_path, abs_cwd):
            return ToolResult(is_error=True, output=f"Error: Access denied. Path '{path}' is outside of workspace.")

        # Protected files check
        if norm_path in context.protected_files:
            return ToolResult(is_error=True, output=f"Archivo protegido: {norm_path}. No se puede modificar vía agente.")

        # Trust check
        if not context.trusted:
            return ToolResult(is_error=True, output="Proyecto no confiado (untrusted). Ejecuta project-trust set antes de escribir.")

        target_dir = os.path.dirname(target_path)
        temp_path = None
        try:
            os.makedirs(target_dir, exist_ok=True)

            # 1. Create a temporary file in the same directory as the target path
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target_dir, delete=False) as temp_file:
                temp_path = temp_file.name
                temp_file.write(content)
                temp_file.flush()
                os.fsync(temp_file.fileno())

            # 2. If target file exists, create a backup copy
            if os.path.exists(target_path):
                backup_path = f"{target_path}.bak"
                shutil.copy2(target_path, backup_path)

            # 3. Atomically replace the original file
            os.replace(temp_path, target_path)
            return ToolResult(output=f"File '{norm_path}' written successfully.")
        except Exception as e:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            return ToolResult(is_error=True, output=f"Error writing file: {str(e)}")
