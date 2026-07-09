from abc import ABC, abstractmethod
from typing import Any, Set
from pydantic import BaseModel

class ToolContext(BaseModel):
    cwd: str
    trusted: bool
    protected_files: Set[str]

class ToolResult(BaseModel):
    output: str
    is_error: bool = False

class AgentTool(ABC):
    name: str
    description: str
    parameters_schema: dict[str, Any]  # Standard JSON Schema

    @abstractmethod
    async def execute(self, arguments: dict[str, Any], context: ToolContext) -> ToolResult:
        ...
