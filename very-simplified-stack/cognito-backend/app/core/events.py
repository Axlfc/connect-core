from typing import Literal, Optional, Any, Union
from pydantic import BaseModel
from app.core.logging_config import get_trace_id

class TextDeltaEvent(BaseModel):
    type: Literal["text_delta"] = "text_delta"
    content: str
    uncertainty: Optional[float] = None
    trace_id: Optional[str] = None

    def __init__(self, **data: Any):
        if "trace_id" not in data or data["trace_id"] is None:
            data["trace_id"] = get_trace_id()
        super().__init__(**data)

class ToolCallEvent(BaseModel):
    type: Literal["tool_call"] = "tool_call"
    tool_call_id: str
    tool_name: str
    arguments: dict[str, Any]
    trace_id: Optional[str] = None

    def __init__(self, **data: Any):
        if "trace_id" not in data or data["trace_id"] is None:
            data["trace_id"] = get_trace_id()
        super().__init__(**data)

class ToolResultEvent(BaseModel):
    type: Literal["tool_result"] = "tool_result"
    tool_call_id: str
    tool_name: str
    output: str
    is_error: bool = False
    trace_id: Optional[str] = None

    def __init__(self, **data: Any):
        if "trace_id" not in data or data["trace_id"] is None:
            data["trace_id"] = get_trace_id()
        super().__init__(**data)

class DoneEvent(BaseModel):
    type: Literal["done"] = "done"
    stop_reason: Literal["end_turn", "tool_use", "max_turns", "error", "aborted"]
    error_message: Optional[str] = None
    trace_id: Optional[str] = None

    def __init__(self, **data: Any):
        if "trace_id" not in data or data["trace_id"] is None:
            data["trace_id"] = get_trace_id()
        super().__init__(**data)

class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    message: str
    trace_id: Optional[str] = None

    def __init__(self, **data: Any):
        if "trace_id" not in data or data["trace_id"] is None:
            data["trace_id"] = get_trace_id()
        super().__init__(**data)

class SessionInfoEvent(BaseModel):
    type: Literal["session_info"] = "session_info"
    session_id: str
    is_new: bool
    trace_id: Optional[str] = None

    def __init__(self, **data: Any):
        if "trace_id" not in data or data["trace_id"] is None:
            data["trace_id"] = get_trace_id()
        super().__init__(**data)

class ApprovalRequiredEvent(BaseModel):
    type: Literal["approval_required"] = "approval_required"
    approval_id: str
    session_id: str
    tool_name: str
    arguments: dict[str, Any]
    reason: str
    timeout_seconds: int
    trace_id: Optional[str] = None

    def __init__(self, **data: Any):
        if "trace_id" not in data or data["trace_id"] is None:
            data["trace_id"] = get_trace_id()
        super().__init__(**data)

AgentEvent = Union[TextDeltaEvent, ToolCallEvent, ToolResultEvent, DoneEvent, ErrorEvent, SessionInfoEvent, ApprovalRequiredEvent]
