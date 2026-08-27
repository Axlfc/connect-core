import logging
import json
import uuid
import contextvars
from typing import Dict, Any, Optional

# ContextVar for logging correlation context and trace_id
correlation_context = contextvars.ContextVar("correlation_context", default={})
TRACE_ID_VAR = contextvars.ContextVar("trace_id", default="")

def get_trace_id() -> str:
    """
    Retrieves the current trace_id from TRACE_ID_VAR, falling back to correlation_context.
    """
    tid = TRACE_ID_VAR.get()
    if not tid:
        tid = correlation_context.get().get("trace_id", "")
    return tid

def set_trace_id(trace_id: Optional[str] = None) -> str:
    """
    Sets the trace_id in contextvars. Generates a new UUID4 string if trace_id is empty or None.
    Returns the effective trace_id.
    """
    if not trace_id:
        trace_id = uuid.uuid4().hex
    TRACE_ID_VAR.set(trace_id)
    set_correlation_ids(trace_id=trace_id)
    return trace_id

def set_correlation_ids(
    task_id: str = "",
    attempt_id: str = "",
    decision_id: str = "",
    worker_id: str = "",
    codex_thread_id: str = "",
    correlation_id: str = "",
    trace_id: str = "",
):
    current = correlation_context.get().copy()
    if task_id: current["task_id"] = task_id
    if attempt_id: current["attempt_id"] = attempt_id
    if decision_id: current["decision_id"] = decision_id
    if worker_id: current["worker_id"] = worker_id
    if codex_thread_id: current["codex_thread_id"] = codex_thread_id
    if correlation_id: current["correlation_id"] = correlation_id
    if trace_id: current["trace_id"] = trace_id
    correlation_context.set(current)

def clear_correlation_context():
    correlation_context.set({})
    TRACE_ID_VAR.set("")

def redact_sensitive_keys(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively redacts likely sensitive keys from dictionaries.
    """
    sensitive_keys = {"authorization", "secret", "hmac", "token", "password", "key", "signature"}
    redacted = {}
    for k, v in data.items():
        if k.lower() in sensitive_keys or any(sk in k.lower() for sk in sensitive_keys):
            redacted[k] = "[REDACTED]"
        elif isinstance(v, dict):
            redacted[k] = redact_sensitive_keys(v)
        else:
            redacted[k] = v
    return redacted

class StructuredJSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        tid = get_trace_id()
        log_data = {
            "timestamp": record.created,
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "filename": record.filename,
            "lineno": record.lineno,
            "trace_id": tid,
            **correlation_context.get()
        }

        # Merge extra fields if present
        if hasattr(record, "extra_fields") and isinstance(record.extra_fields, dict):
            log_data.update(redact_sensitive_keys(record.extra_fields))

        return json.dumps(log_data)

def configure_structured_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Remove existing handlers
    for h in logger.handlers[:]:
        logger.removeHandler(h)

    handler = logging.StreamHandler()
    handler.setFormatter(StructuredJSONFormatter())
    logger.addHandler(handler)
