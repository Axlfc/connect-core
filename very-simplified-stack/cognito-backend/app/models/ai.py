from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

class AIRequest(BaseModel):
    prompt: str
    session_id: Optional[str] = None
    system_prompt: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None

class AIResponse(BaseModel):
    response: str
    session_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        populate_by_name = True

    def __init__(self, **data: Any):
        if "text" in data and "response" not in data:
            data["response"] = data["text"]
        super().__init__(**data)

    @property
    def text(self) -> str:
        return self.response

    @text.setter
    def text(self, value: str):
        self.response = value
