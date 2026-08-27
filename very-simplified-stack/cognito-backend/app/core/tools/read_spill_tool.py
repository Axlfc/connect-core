from pathlib import Path
from typing import Any, Dict, List, Optional
from app.core.tools.base import AgentTool, ToolContext, ToolResult
from app.core.context_spill import DEFAULT_SPILL_DIR

class ReadSpillTool(AgentTool):
    name = "read_spill"
    description = (
        "Lee el contenido de un spill de contexto desbordado por su spill_id. "
        "Devuelve el contenido completo o un fragmento si se solicita un rango de líneas."
    )
    is_read_only = True
    is_destructive = False
    concurrency_safe = True
    parameters_schema = {
        "type": "object",
        "properties": {
            "spill_id": {
                "type": "string",
                "description": "El identificador del contenido almacenado (ej. spill_abc123)."
            },
            "start_line": {
                "type": "integer",
                "description": "Línea inicial a consultar (1-indexed)."
            },
            "end_line": {
                "type": "integer",
                "description": "Línea final a consultar (1-indexed)."
            },
            "line_range": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "Opcional: Rango de líneas [línea_inicio, línea_fin] (1-indexed)."
            }
        },
        "required": ["spill_id"]
    }

    def __init__(self, spill_dir: Optional[Path] = None):
        self.spill_dir = Path(spill_dir) if spill_dir else DEFAULT_SPILL_DIR

    async def execute(self, arguments: Dict[str, Any], context: ToolContext) -> ToolResult:
        spill_id = arguments.get("spill_id")
        if not spill_id:
            return ToolResult(is_error=True, output="Error: spill_id es requerido.")

        safe_id = Path(spill_id).name
        if not safe_id.endswith(".txt"):
            safe_id = f"{safe_id}.txt"

        target_file = self.spill_dir / safe_id
        if not target_file.exists() or not target_file.is_file():
            return ToolResult(is_error=True, output=f"Spill con ID '{spill_id}' no encontrado o expirado.")

        try:
            content = target_file.read_text(encoding="utf-8")
        except Exception as e:
            return ToolResult(is_error=True, output=f"Error leyendo el spill '{spill_id}': {e}")

        # Extract line ranges if specified
        line_range = arguments.get("line_range")
        start_line = arguments.get("start_line")
        end_line = arguments.get("end_line")

        if line_range and len(line_range) >= 2:
            start_line = line_range[0]
            end_line = line_range[1]

        if start_line is not None or end_line is not None:
            lines = content.splitlines()
            total_lines = len(lines)
            s_line = start_line if start_line is not None else 1
            e_line = end_line if end_line is not None else total_lines

            start_idx = max(0, s_line - 1)
            end_idx = min(total_lines, e_line)

            selected_lines = lines[start_idx:end_idx]
            return ToolResult(output="\n".join(selected_lines))

        return ToolResult(output=content)
