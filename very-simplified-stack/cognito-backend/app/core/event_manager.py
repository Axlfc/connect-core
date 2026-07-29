import time
import json
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class ShortTermEvent(BaseModel):
    event_type: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)

class EventManager:
    """
    Chronological registry of events acting as short-term memory (NOOA-08).
    Keeps trace logs, thoughts, tool invocations, etc.
    """
    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id or f"session_{int(time.time())}"
        self.events: List[ShortTermEvent] = []

    def record_event(self, event_type: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> ShortTermEvent:
        evt = ShortTermEvent(event_type=event_type, content=content, metadata=metadata or {})
        self.events.append(evt)
        return evt

    def get_recent_events(self, limit: int = 20, filter_type: Optional[str] = None) -> List[ShortTermEvent]:
        lst = self.events
        if filter_type:
            lst = [e for e in lst if e.event_type == filter_type]
        return lst[-limit:]

    def clear(self):
        self.events.clear()

    def summarize_short_term(self) -> str:
        """
        Creates a structured text summary of the current execution log for LLM intake.
        """
        lines = []
        for e in self.events:
            lines.append(f"[{time.strftime('%H:%M:%S', time.gmtime(e.timestamp))}] {e.event_type.upper()}: {e.content}")
        return "\n".join(lines)
