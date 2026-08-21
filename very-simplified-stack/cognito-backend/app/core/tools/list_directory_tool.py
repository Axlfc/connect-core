from pathlib import Path
from typing import Any, Dict
from app.core.tools.base import AgentTool, ToolContext, ToolResult
from app.core.fs_observation_policy import FSObservationPolicy

class ListDirectoryTool(AgentTool):
    name = "list_directory"
    description = "List files and directories in a given path relative to cwd."
    parameters_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Directory path relative to cwd. Defaults to '.'", "default": "."},
        },
    }

    async def execute(self, arguments: Dict[str, Any], context: ToolContext) -> ToolResult:
        dir_str = arguments.get("path", ".") or "."
        GENERIC_ERROR = "Archivo o directorio no encontrado o no accesible"

        cwd_path = Path(context.cwd).resolve()
        policy = FSObservationPolicy(
            cwd=cwd_path,
            protected_files=getattr(context, "protected_files", None)
        )

        if policy.is_hidden(dir_str):
            return ToolResult(is_error=True, output=GENERIC_ERROR)

        try:
            target_dir = (cwd_path / Path(dir_str)).resolve()
        except Exception:
            return ToolResult(is_error=True, output=GENERIC_ERROR)

        if not target_dir.exists() or not target_dir.is_dir():
            return ToolResult(is_error=True, output=GENERIC_ERROR)

        try:
            entries = []
            for item in sorted(target_dir.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
                try:
                    rel_item = item.relative_to(cwd_path)
                except ValueError:
                    continue

                if not policy.is_hidden(rel_item):
                    item_type = "[DIR]" if item.is_dir() else "[FILE]"
                    entries.append(f"{item_type} {item.name}")

            output = "\n".join(entries) if entries else "Directorio vacío."
            return ToolResult(output=output)
        except Exception as e:
            return ToolResult(is_error=True, output=f"Error listing directory: {str(e)}")
