from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class PromptTestCase(BaseModel):
    id: str
    category: str  # e.g., identity, tone, tool_rules, honesty, safety, agents_md_override
    description: str
    user_prompt: str
    required_keywords: List[str] = Field(default_factory=list)
    forbidden_keywords: List[str] = Field(default_factory=list)
    expected_principles: List[str] = Field(default_factory=list)

class EvalResultCase(BaseModel):
    case_id: str
    category: str
    passed: bool
    score: float
    matched_rules: List[str]
    failed_rules: List[str]

class SystemPromptEvalReport(BaseModel):
    version: str
    total_cases: int
    passed_cases: int
    pass_rate: float
    category_scores: Dict[str, float]
    results: List[EvalResultCase]
