import os
import json
import logging
import re
from typing import List, Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)

# Configurable constants via environment variables
COMPACTION_THRESHOLD_TOKENS = int(os.getenv("COGNITO_SESSION_COMPACTION_THRESHOLD_TOKENS", "8000"))
KEEP_LAST_N_MESSAGES = int(os.getenv("COGNITO_SESSION_KEEP_LAST_N_MESSAGES", "6"))

COMPACTION_SYSTEM_PROMPT = """Resume todos los mensajes anteriores de esta conversación de forma concisa.
ES CRÍTICO que preservas:
1. Decisiones clave tomadas por el usuario o el asistente.
2. Archivos que han sido leídos, escritos o editados.
3. Tareas pendientes que el usuario ha solicitado.
4. Cualquier restricción o advertencia mencionada (especialmente si se rechazó el acceso a un archivo protegido).

Devuelve únicamente el texto del resumen, sin preámbulos ni explicaciones adicionales."""

FILE_PATH_KEY_NAMES = {"filepath", "path", "filename", "file", "target", "source", "destination", "files", "file_path", "file_paths"}

def _parse_embedded_ledgers(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    merged_files = []
    merged_signatures = []
    merged_tools = []

    for msg in messages:
        if not isinstance(msg, dict):
            continue

        cl = msg.get("context_ledger")
        if isinstance(cl, dict):
            if "files_touched" in cl and isinstance(cl["files_touched"], list):
                merged_files.extend(cl["files_touched"])
            if "function_signatures" in cl and isinstance(cl["function_signatures"], list):
                merged_signatures.extend(cl["function_signatures"])
            if "tool_calls" in cl and isinstance(cl["tool_calls"], list):
                merged_tools.extend(cl["tool_calls"])

        content = msg.get("content", "") or ""
        if "Context Ledger" in content or "files_touched" in content:
            matches = re.findall(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
            for m in matches:
                try:
                    data = json.loads(m)
                    if isinstance(data, dict):
                        if "files_touched" in data and isinstance(data["files_touched"], list):
                            merged_files.extend(data["files_touched"])
                        if "function_signatures" in data and isinstance(data["function_signatures"], list):
                            merged_signatures.extend(data["function_signatures"])
                        if "tool_calls" in data and isinstance(data["tool_calls"], list):
                            merged_tools.extend(data["tool_calls"])
                except Exception:
                    pass
    return {
        "files_touched": merged_files,
        "function_signatures": merged_signatures,
        "tool_calls": merged_tools
    }

def extract_context_ledger(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    files_touched = []
    function_signatures = []
    tool_calls_summary = []

    # 1. Parse prior ledger(s) if present
    prior_ledger = _parse_embedded_ledgers(messages)
    for f in prior_ledger.get("files_touched", []):
        if f and f not in files_touched:
            files_touched.append(f)
    for sig in prior_ledger.get("function_signatures", []):
        if sig and sig not in function_signatures:
            function_signatures.append(sig)
    for tc in prior_ledger.get("tool_calls", []):
        if tc and tc not in tool_calls_summary:
            tool_calls_summary.append(tc)

    sig_pattern = re.compile(
        r'((?:async\s+)?def\s+[a-zA-Z_]\w*\s*\([^)]*\)(?:\s*->\s*[^:\n]+)?|class\s+[a-zA-Z_]\w*(?:\([^)]*\))?)'
    )
    filepath_pattern = re.compile(
        r'\b([a-zA-Z0-9_\-\.]+/[a-zA-Z0-9_\-\./]+\.[a-zA-Z0-9]{1,10})\b'
    )

    for msg in messages:
        content = msg.get("content", "") or ""

        # Extract function/class signatures from content
        for match in sig_pattern.findall(content):
            sig_clean = match.strip()
            if sig_clean and sig_clean not in function_signatures and not sig_clean.startswith("```"):
                function_signatures.append(sig_clean)

        # Extract file paths from content
        for match in filepath_pattern.findall(content):
            fp_clean = match.strip()
            if fp_clean and not fp_clean.startswith(("http://", "https://")) and fp_clean not in files_touched:
                files_touched.append(fp_clean)

        # Process tool calls
        tool_calls = msg.get("tool_calls")
        if tool_calls and isinstance(tool_calls, list):
            for tc in tool_calls:
                if not isinstance(tc, dict):
                    continue
                func_data = tc.get("function", {}) if isinstance(tc.get("function"), dict) else {}
                tool_name = func_data.get("name") or tc.get("name") or tc.get("tool_name") or "unknown"
                args_raw = func_data.get("arguments") or tc.get("arguments") or tc.get("args") or {}

                args_dict = {}
                if isinstance(args_raw, str):
                    try:
                        args_dict = json.loads(args_raw)
                    except Exception:
                        args_dict = {"raw": args_raw[:100]}
                elif isinstance(args_raw, dict):
                    args_dict = args_raw

                if isinstance(args_dict, dict):
                    for k, v in args_dict.items():
                        if k.lower() in FILE_PATH_KEY_NAMES and isinstance(v, str):
                            if v and v not in files_touched:
                                files_touched.append(v)
                        elif (k.lower() in FILE_PATH_KEY_NAMES or k.lower().endswith("files") or k.lower().endswith("paths")) and isinstance(v, list):
                            for item in v:
                                if isinstance(item, str) and item not in files_touched:
                                    files_touched.append(item)

                key_args = {}
                if isinstance(args_dict, dict):
                    for k, v in args_dict.items():
                        if isinstance(v, str):
                            key_args[k] = v if len(v) <= 120 else v[:117] + "..."
                        elif isinstance(v, (int, float, bool)):
                            key_args[k] = v
                        elif isinstance(v, list):
                            key_args[k] = f"list(len={len(v)})"
                        elif isinstance(v, dict):
                            key_args[k] = f"dict(keys={list(v.keys())})"
                else:
                    key_args = {"raw": str(args_dict)[:100]}

                tc_summary = {"name": tool_name, "args": key_args}
                if tc_summary not in tool_calls_summary:
                    tool_calls_summary.append(tc_summary)

        if msg.get("role") == "tool" or "tool_name" in msg:
            tname = msg.get("name") or msg.get("tool_name") or "unknown"
            if tname and not any(tc.get("name") == tname for tc in tool_calls_summary):
                tool_calls_summary.append({"name": tname, "args": {}})

    return {
        "files_touched": files_touched,
        "function_signatures": function_signatures,
        "tool_calls": tool_calls_summary
    }

def format_ledger_for_system_prompt(ledger: Dict[str, Any]) -> str:
    if not ledger:
        return ""
    files = ledger.get("files_touched", [])
    signatures = ledger.get("function_signatures", [])
    tools = ledger.get("tool_calls", [])

    lines = ["[Context Ledger / Detalle Estructural]:"]
    if files:
        lines.append("- Archivos tocados: " + ", ".join(files))
    if signatures:
        lines.append("- Firmas/Estructuras relevantes:")
        for sig in signatures:
            lines.append(f"  * {sig}")
    if tools:
        lines.append("- Historial de herramientas ejecutadas:")
        for t in tools:
            name = t.get("name", "unknown")
            args = t.get("args", {})
            args_str = json.dumps(args, ensure_ascii=False) if isinstance(args, dict) else str(args)
            lines.append(f"  * {name}({args_str})")

    lines.append("```json")
    lines.append(json.dumps(ledger, indent=2, ensure_ascii=False))
    lines.append("```")
    return "\n".join(lines)

async def should_compact(effective_messages: List[Dict], threshold_tokens: int = COMPACTION_THRESHOLD_TOKENS) -> bool:
    """
    Heuristic token count: chars // 4.
    Returns True if threshold is exceeded.
    """
    if len(effective_messages) <= KEEP_LAST_N_MESSAGES + 2: # Don't compact very short history
        return False

    total_chars = 0
    for msg in effective_messages:
        content = msg.get("content", "") or ""
        total_chars += len(content)
        # Also count tool names and IDs if present
        if "name" in msg: total_chars += len(msg["name"])
        if "tool_call_id" in msg: total_chars += len(msg["tool_call_id"])

    estimated_tokens = total_chars // 4
    return estimated_tokens > threshold_tokens

async def compact(
    effective_messages: List[Dict],
    keep_last_n: int = KEEP_LAST_N_MESSAGES,
    backend_router = None,
) -> Tuple[str, Dict[str, Any]]:
    """
    Summarizes messages except the last N using the backend router,
    and returns a tuple of (summary, context_ledger).
    """
    if not backend_router:
        from app.services.backend_router import backend_router as global_router
        backend_router = global_router

    # Separate messages to compact and messages to keep
    to_compact = effective_messages[:-keep_last_n] if keep_last_n > 0 else effective_messages
    context_ledger = extract_context_ledger(to_compact)

    # Format to_compact for the prompt
    history_text = ""
    for msg in to_compact:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        history_text += f"[{role}]: {content}\n\n"

    prompt = f"{COMPACTION_SYSTEM_PROMPT}\n\nHistorial a resumir:\n{history_text}"

    try:
        logger.info(f"Triggering compaction for {len(to_compact)} messages")
        result = await backend_router.generate(prompt=prompt)
        summary = result.get("response", "").strip()
        if not summary:
            logger.warning("Compaction generated an empty summary.")
            summary = "Resumen no disponible por error del modelo."
        return summary, context_ledger
    except Exception as e:
        logger.error(f"Failed to generate compaction summary: {e}", exc_info=True)
        raise e
