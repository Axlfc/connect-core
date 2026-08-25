import json
import hashlib
import logging
from collections import deque
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


def normalize_args(args: Any) -> str:
    """
    Normalizes tool call arguments into a deterministic JSON string representation.
    Handles dictionaries, lists, primitive values, and raw JSON strings.
    """
    if isinstance(args, str):
        # Attempt to parse as JSON if it's a JSON string
        try:
            parsed = json.loads(args)
            return json.dumps(parsed, sort_keys=True, separators=(',', ':'))
        except (json.JSONDecodeError, TypeError):
            return args.strip()

    if isinstance(args, (dict, list)):
        try:
            return json.dumps(args, sort_keys=True, separators=(',', ':'))
        except (TypeError, ValueError):
            return str(args)

    return str(args)


def compute_tool_call_hash(tool_name: str, args: Any, output: Optional[str] = None) -> str:
    """
    Computes a SHA-256 hash of (tool_name, normalized_args, output).
    If output is provided, includes output hash to distinguish calls that yield different results.
    """
    normalized = normalize_args(args)
    if output is not None:
        out_hash = hashlib.sha256(str(output).encode("utf-8")).hexdigest()
        payload = f"{tool_name}:{normalized}:{out_hash}"
    else:
        payload = f"{tool_name}:{normalized}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


READ_ONLY_TOOLS = {
    "read",
    "read_file",
    "list_directory",
    "search_files",
    "query_spill",
    "read_spill",
}


class ToolLoopDetector:
    """
    Rolling window detector for repeated tool calls.
    Keeps track of the last N tool call hashes during the current turn/session.
    If `threshold` or more identical consecutive calls occur, activates the guardrail warning.
    """

    WARNING_TEMPLATE = (
        "ADVERTENCIA DEL SISTEMA: Has intentado ejecutar la herramienta '{tool_name}' "
        "con los mismos parámetros múltiples veces sin éxito. Detén este patrón. "
        "Reevalúa tu estrategia, verifica los mensajes de error anteriores o solicita ayuda al usuario."
    )

    def __init__(self, window_size: int = 10, threshold: int = 3):
        """
        :param window_size: Size of the rolling window of recent tool call hashes (default N=10).
        :param threshold: Number of identical consecutive tool calls required to activate guardrail (default 3).
        """
        self.window_size = window_size
        self.threshold = threshold
        self.history: deque[Tuple[str, str]] = deque(maxlen=window_size)  # stores (tool_name, hash)

    def record_and_check(self, tool_name: str, arguments: Any, output: Optional[str] = None) -> Optional[str]:
        """
        Records a tool call into the rolling window and checks if the loop threshold is exceeded.

        :param tool_name: Name of the executed tool.
        :param arguments: Tool arguments.
        :param output: Execution result of the tool call. If provided, used to determine if output changed.
        :return: Optional warning string to inject as system message if guardrail triggers, else None.
        """
        if tool_name in READ_ONLY_TOOLS:
            call_hash = compute_tool_call_hash(tool_name, arguments, output=output)
        else:
            call_hash = compute_tool_call_hash(tool_name, arguments, output=None)

        self.history.append((tool_name, call_hash))

        # Check consecutive matches from the end of history
        consecutive_count = 0
        for name, h in reversed(self.history):
            if h == call_hash:
                consecutive_count += 1
            else:
                break

        if consecutive_count >= self.threshold:
            logger.warning(
                f"ToolLoopDetector triggered for tool '{tool_name}'! "
                f"Consecutive identical calls count: {consecutive_count}"
            )
            return self.WARNING_TEMPLATE.format(tool_name=tool_name)

        return None

    def reset(self):
        """Resets the history window."""
        self.history.clear()
