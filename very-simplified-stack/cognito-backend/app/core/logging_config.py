import logging
import json
import contextvars
from typing import Dict, Any

# ContextVar for logging correlation context
correlation_context = contextvars.ContextVar("correlation_context", default={})

def set_correlation_ids(task_id: str = "", attempt_id: str = "", decision_id: str = "", worker_id: str = "", codex_thread_id: str = "", correlation_id: str = ""):
    current = correlation_context.get().copy()
    if task_id: current["task_id"] = task_id
    if attempt_id: current["attempt_id"] = attempt_id
    if decision_id: current["decision_id"] = decision_id
    if worker_id: current["worker_id"] = worker_id
    if codex_thread_id: current["codex_thread_id"] = codex_thread_id
    if correlation_id: current["correlation_id"] = correlation_id
    correlation_context.set(current)

def clear_correlation_context():
    correlation_context.set({})

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
        log_data = {
            "timestamp": record.created,
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "filename": record.filename,
            "lineno": record.lineno,
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
