from typing import Callable, Awaitable, Literal, Optional, Dict, List, Any
from pydantic import BaseModel

class SessionStartPayload(BaseModel):
    session_id: str
    cwd: str
    is_new: bool

class BeforeToolCallPayload(BaseModel):
    session_id: str
    cwd: str
    tool_name: str
    arguments: Dict[str, Any]

class AfterToolCallPayload(BaseModel):
    session_id: str
    cwd: str
    tool_name: str
    arguments: Dict[str, Any]
    output: str
    is_error: bool

class MessageEndPayload(BaseModel):
    session_id: str
    cwd: str
    role: str
    content: str
    tool_name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None

class AgentStartPayload(BaseModel):
    session_id: Optional[str] = None
    cwd: str
    messages: List[Dict[str, Any]]
    model_name: Optional[str] = None
    max_turns: int = 10
    trace_id: Optional[str] = None

class ToolPreExecPayload(BaseModel):
    session_id: Optional[str] = None
    cwd: str
    tool_name: str
    arguments: Dict[str, Any]
    tool_call_id: str
    turn: int = 1
    trace_id: Optional[str] = None

class ToolPostExecPayload(BaseModel):
    session_id: Optional[str] = None
    cwd: str
    tool_name: str
    arguments: Dict[str, Any]
    tool_call_id: str
    output: str
    is_error: bool
    turn: int = 1
    trace_id: Optional[str] = None

class PreCompactPayload(BaseModel):
    session_id: Optional[str] = None
    cwd: Optional[str] = None
    messages: List[Dict[str, Any]]
    threshold_tokens: Optional[int] = None
    keep_last_n: Optional[int] = None
    trace_id: Optional[str] = None

HookEvent = Literal[
    "session_start", "before_tool_call", "after_tool_call", "message_end",
    "on_agent_start", "on_tool_pre_exec", "on_tool_post_exec", "on_pre_compact"
]

class ExtensionAPI:
    def __init__(self, registry: "ExtensionRegistry", origin: Optional[str]):
        # origin=None -> Global/Configured. origin=<cwd> -> Local al proyecto.
        self._registry = registry
        self._origin = origin

    def register_tool(self, tool: Any) -> None:
        self._registry.register_tool(tool, self._origin)

    def register_backend(self, config: Any) -> None:
        if self._origin is not None:
            import logging
            logging.getLogger("cognito.extensions").warning(
                f"Ignored register_backend from project-local extension at {self._origin}"
            )
            return
        self._registry.register_backend(config)

    def register_intent(self, intent: str, backend_name: str, model: str) -> None:
        if self._origin is not None:
            import logging
            logging.getLogger("cognito.extensions").warning(
                f"Ignored register_intent from project-local extension at {self._origin}"
            )
            return
        self._registry.register_intent(intent, backend_name, model)

    def on(self, event: HookEvent, handler: Callable[[Any], Awaitable[Optional[str]]]) -> None:
        self._registry.register_hook(event, handler, self._origin)

    def on_agent_start(self, handler: Callable[[AgentStartPayload], Awaitable[Optional[str]]]) -> None:
        self.on("on_agent_start", handler)

    def on_tool_pre_exec(self, handler: Callable[[ToolPreExecPayload], Awaitable[Optional[str]]]) -> None:
        self.on("on_tool_pre_exec", handler)

    def on_tool_post_exec(self, handler: Callable[[ToolPostExecPayload], Awaitable[Optional[str]]]) -> None:
        self.on("on_tool_post_exec", handler)

    def on_pre_compact(self, handler: Callable[[PreCompactPayload], Awaitable[Optional[str]]]) -> None:
        self.on("on_pre_compact", handler)
