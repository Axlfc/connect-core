import sys
import os
import logging
from typing import Optional, Tuple
from app.core.project_trust import ProjectTrustStore
from app.core.session_manager import SessionManager
from app.core.compaction import compact

logger = logging.getLogger("cognito-cli.slash")

async def handle_slash_command(
    command_line: str,
    cwd: str,
    current_session_id: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """
    Handles slash commands locally without sending to LLM.
    Returns (handled, updated_session_id).
    If command_line starts with '/', handled is True.
    """
    raw = command_line.strip()
    if not raw.startswith("/"):
        return False, current_session_id

    parts = raw.split(maxsplit=1)
    cmd = parts[0].lower()
    args_str = parts[1].strip() if len(parts) > 1 else ""

    trust_store = ProjectTrustStore()

    if cmd == "/clear":
        sys.stdout.write("\033[H\033[2J")
        sys.stdout.flush()
        print("[Pantalla y contexto visual limpiados]")
        return True, current_session_id

    elif cmd == "/status":
        is_trusted = trust_store.is_trusted(cwd)
        session_str = current_session_id if current_session_id else "Sin sesión activa"
        print("=== Cognito Status ===")
        print(f"Session ID: {session_str}")
        print(f"CWD: {cwd}")
        print(f"Trusted: {is_trusted}")
        return True, current_session_id

    elif cmd == "/trust":
        current_status = trust_store.is_trusted(cwd)
        new_status = not current_status

        if args_str:
            val = args_str.lower()
            if val in ("on", "true", "yes", "1", "trust", "trusted"):
                new_status = True
            elif val in ("off", "false", "no", "0", "untrust", "untrusted"):
                new_status = False

        trust_store.set_trusted(cwd, new_status)
        print(f"[Nivel de confianza actualizado: trusted={new_status}]")
        return True, current_session_id

    elif cmd == "/compact":
        if not current_session_id:
            print("[Advertencia: No hay sesión activa para compactar.]")
            return True, current_session_id

        try:
            session_manager = SessionManager()
            effective_messages = session_manager.get_effective_messages(current_session_id)
            if not effective_messages:
                print(f"[La sesión {current_session_id} está vacía o no tiene mensajes para compactar.]")
                return True, current_session_id

            last_line = session_manager.get_last_line_index(current_session_id)
            summary, context_ledger = await compact(effective_messages)
            session_manager.append_compaction(current_session_id, summary, last_line, context_ledger)
            print(f"[Sesión {current_session_id} compactada exitosamente.]")
        except Exception as e:
            logger.error(f"Error al compactar sesión: {e}")
            print(f"[Error al compactar sesión {current_session_id}: {str(e)}]")

        return True, current_session_id

    else:
        print(f"[Comando no reconocido: {cmd}. Comandos disponibles: /clear, /status, /trust, /compact]")
        return True, current_session_id
