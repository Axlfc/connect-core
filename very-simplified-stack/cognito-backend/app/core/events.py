from typing import Literal, Optional, Any, Union
from pydantic import BaseModel

class TextDeltaEvent(BaseModel):
    type: Literal["text_delta"] = "text_delta"
    content: str
    uncertainty: Optional[float] = None

class ToolCallEvent(BaseModel):
    type: Literal["tool_call"] = "tool_call"
    tool_call_id: str
    tool_name: str
    arguments: dict[str, Any]

class ToolResultEvent(BaseModel):
    type: Literal["tool_result"] = "tool_result"
    tool_call_id: str
    tool_name: str
    output: str
    is_error: bool = False

class DoneEvent(BaseModel):
    type: Literal["done"] = "done"
    stop_reason: Literal["end_turn", "tool_use", "max_turns", "error", "aborted"]
    error_message: Optional[str] = None

class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    message: str

class SessionInfoEvent(BaseModel):
    type: Literal["session_info"] = "session_info"
    session_id: str
    is_new: bool

AgentEvent = Union[TextDeltaEvent, ToolCallEvent, ToolResultEvent, DoneEvent, ErrorEvent, SessionInfoEvent]
