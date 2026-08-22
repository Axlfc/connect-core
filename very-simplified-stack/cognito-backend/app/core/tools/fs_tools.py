import fnmatch
import os
from pathlib import Path
from typing import Any, Dict
from app.core.tools.base import AgentTool, ToolContext, ToolResult
from app.core.fs_observation_policy import FSObservationPolicy


class ListDirectoryTool(AgentTool):
    name = "list_directory"
    description = "List contents of a directory. Hides protected and ignored files/folders."
    parameters_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to directory relative to cwd.", "default": "."},
        },
    }

    async def execute(self, arguments: Dict[str, Any], context: ToolContext) -> ToolResult:
        dir_path_str = arguments.get("path", ".") or "."
        policy = FSObservationPolicy(
            cwd=context.cwd,
            protected_files=getattr(context, "protected_files", None),
        )

        target_dir = Path(context.cwd) / dir_path_str

        if policy.is_path_ignored(target_dir):
            return ToolResult(is_error=True, output=policy.get_generic_error_message())

        resolved_dir = target_dir.resolve()
        if not resolved_dir.exists() or not resolved_dir.is_dir():
            return ToolResult(is_error=True, output=policy.get_generic_error_message())

        try:
            entries = list(resolved_dir.iterdir())
            allowed_entries = policy.filter_paths(entries)

            lines = []
            for entry in sorted(allowed_entries, key=lambda p: p.name.lower()):
                kind = "[DIR]" if entry.is_dir() else "[FILE]"
                lines.append(f"{kind} {entry.name}")

            output = "\n".join(lines) if lines else "Directorio vacío"
            return ToolResult(output=output)
        except Exception:
            return ToolResult(is_error=True, output=policy.get_generic_error_message())


class SearchFilesTool(AgentTool):
    name = "search_files"
    description = "Search for files matching a pattern in workspace. Hides protected and ignored files."
    parameters_schema = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "File pattern to match, e.g. '*.py' or '*test*'"},
            "path": {"type": "string", "description": "Starting directory relative to cwd.", "default": "."},
        },
        "required": ["pattern"],
    }

    async def execute(self, arguments: Dict[str, Any], context: ToolContext) -> ToolResult:
        pattern = arguments.get("pattern", "*")
        start_path_str = arguments.get("path", ".") or "."

        policy = FSObservationPolicy(
            cwd=context.cwd,
            protected_files=getattr(context, "protected_files", None),
        )

        start_dir = Path(context.cwd) / start_path_str

        if policy.is_path_ignored(start_dir):
            return ToolResult(is_error=True, output=policy.get_generic_error_message())

        resolved_start = start_dir.resolve()
        if not resolved_start.exists() or not resolved_start.is_dir():
            return ToolResult(is_error=True, output=policy.get_generic_error_message())

        try:
            matches: list[Path] = []
            for root, dirs, files in os.walk(resolved_start):
                root_path = Path(root)

                # Filter directories in-place so os.walk does not descend into ignored dirs
                dirs[:] = [d for d in dirs if not policy.is_path_ignored(root_path / d)]

                for file in files:
                    file_path = root_path / file
                    if fnmatch.fnmatch(file, pattern) and not policy.is_path_ignored(file_path):
                        matches.append(file_path)

            lines = []
            cwd_path = Path(context.cwd).resolve()
            for m in sorted(matches, key=lambda p: str(p)):
                try:
                    rel = m.resolve().relative_to(cwd_path)
                    lines.append(str(rel))
                except ValueError:
                    lines.append(str(m))

            output = "\n".join(lines) if lines else "No se encontraron archivos coincidentes"
            return ToolResult(output=output)
        except Exception:
            return ToolResult(is_error=True, output=policy.get_generic_error_message())
