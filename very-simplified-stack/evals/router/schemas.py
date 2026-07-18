from pydantic import BaseModel
from typing import List, Optional, Literal

class LabeledTestCase(BaseModel):
    id: str
    user_task: str
    expected_executor: Literal["Ollama", "Codex"]
    expected_logical_tier: Literal["local", "luna", "terra", "sol"]
    risk: Literal["low", "medium", "high"]
    is_high_risk: bool = False
    sensitive_path_indicators: List[str] = []
    category: str = "general"
