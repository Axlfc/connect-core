import os
import json
import logging
from typing import List, Dict

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
) -> str:
    """
    Summarizes messages except the last N using the backend router.
    """
    if not backend_router:
        from app.services.backend_router import backend_router as global_router
        backend_router = global_router

    # Separate messages to compact and messages to keep
    to_compact = effective_messages[:-keep_last_n] if keep_last_n > 0 else effective_messages

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
            return "Resumen no disponible por error del modelo."
        return summary
    except Exception as e:
        logger.error(f"Failed to generate compaction summary: {e}", exc_info=True)
        raise e
