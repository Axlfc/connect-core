import re
import uuid
import logging
import contextvars
from typing import Dict, Any, List, Optional
from app.core.logging_config import TRACE_ID_VAR, get_trace_id, set_trace_id

logger = logging.getLogger(__name__)

# Context variables for session trace grouping
SESSION_ID_VAR = contextvars.ContextVar("session_id", default="")
TASK_ID_VAR = contextvars.ContextVar("task_id", default="")

# Common sensitive patterns (regexes) for trace scrubbing
SENSITIVE_PATTERNS = [
    re.compile(r"(sk-[a-zA-Z0-9]{32,})"),       # OpenAI API Keys
    re.compile(r"([pP]assword|[cC]ontrase[ñN]a)\s*=\s*['\"][^'\"]+['\"]"),
    re.compile(r"([a-zA-Z0-9\._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})"), # Email address
]

class TraceScrubber:
    """
    Automatic scrubbing of secrets, tokens and passwords in spans / traces (NOOA-20).
    """
    @staticmethod
    def scrub_text(text: str) -> str:
        if not text:
            return text
        for pattern in SENSITIVE_PATTERNS:
            text = pattern.sub("[REDACTED]", text)
        return text

    @classmethod
    def scrub_dict(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        scrubbed = {}
        for k, v in data.items():
            if isinstance(v, str):
                scrubbed[k] = cls.scrub_text(v)
            elif isinstance(v, dict):
                scrubbed[k] = cls.scrub_dict(v)
            elif isinstance(v, list):
                scrubbed[k] = [cls.scrub_dict(item) if isinstance(item, dict) else (cls.scrub_text(item) if isinstance(item, str) else item) for item in v]
            else:
                scrubbed[k] = v
        return scrubbed

class OpenInferenceSpan:
    def __init__(self, name: str, span_type: str = "llm"):
        self.name = name
        self.span_type = span_type
        self.session_id = SESSION_ID_VAR.get()
        self.task_id = TASK_ID_VAR.get()
        self.trace_id = get_trace_id()
        self.inputs: Dict[str, Any] = {}
        self.outputs: Dict[str, Any] = {}

    def set_inputs(self, inputs: Dict[str, Any]):
        self.inputs = TraceScrubber.scrub_dict(inputs)

    def set_outputs(self, outputs: Dict[str, Any]):
        self.outputs = TraceScrubber.scrub_dict(outputs)

    def export(self):
        """
        Simulate exporting via OTel/OpenInference collector.
        """
        logger.info(
            f"[OTEL TRACE] Name: {self.name} | Type: {self.span_type} | "
            f"Trace: {self.trace_id} | Session: {self.session_id} | Task: {self.task_id} | "
            f"Inputs: {self.inputs} | Outputs: {self.outputs}"
        )
