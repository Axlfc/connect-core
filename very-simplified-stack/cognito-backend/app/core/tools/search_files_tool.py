import fnmatch
from pathlib import Path
from typing import Any, Dict
from app.core.tools.base import AgentTool, ToolContext, ToolResult
from app.core.fs_observation_policy import FSObservationPolicy

class SearchFilesTool(AgentTool):
    name = "search_files"
    description = "Search for files matching a pattern or query within a directory."
    parameters_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Base directory to search in, relative to cwd. Defaults to '.'", "default": "."},
            "pattern": {"type": "string", "description": "Filename pattern to match (e.g. '*.py'). Defaults to '*'", "default": "*"},
            "query": {"type": "string", "description": "Optional text query to search inside file contents."},
            "max_results": {"type": "integer", "description": "Maximum number of files to return.", "default": 50},
        },
    }

    async def execute(self, arguments: Dict[str, Any], context: ToolContext) -> ToolResult:
        dir_str = arguments.get("path", ".") or "."
        pattern = arguments.get("pattern", "*") or "*"
        query = arguments.get("query")
        max_results = arguments.get("max_results", 50)

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

        matches = []
        try:
            for item in target_dir.rglob("*"):
                try:
                    rel_item = item.relative_to(cwd_path)
                except ValueError:
                    continue

                if policy.is_hidden(rel_item):
                    continue

                if item.is_file() and fnmatch.fnmatch(item.name, pattern):
                    if query:
                        try:
                            content = item.read_text(encoding="utf-8", errors="ignore")
                            if query.lower() not in content.lower():
                                continue
                        except Exception:
                            continue

                    matches.append(rel_item.as_posix())
                    if len(matches) >= max_results:
                        break

            output = "\n".join(sorted(matches)) if matches else "No se encontraron archivos."
            return ToolResult(output=output)
        except Exception as e:
            return ToolResult(is_error=True, output=f"Error searching files: {str(e)}")
