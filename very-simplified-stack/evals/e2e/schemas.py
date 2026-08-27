from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

class VerificationCriterion(BaseModel):
    criterion_type: str = Field(..., description="file_exists, file_content_contains, file_content_equals, file_deleted, test_passes, event_occurred")
    target: str = Field(..., description="File path, command string, or event name")
    expected_value: Optional[Any] = Field(None, description="Expected text or status")

class E2ETaskCase(BaseModel):
    id: str
    name: str
    category: str
    description: str
    user_prompt: str
    initial_files: Dict[str, str] = Field(default_factory=dict)
    expected_tool_calls: List[str] = Field(default_factory=list)
    verification_criteria: List[VerificationCriterion] = Field(default_factory=list)
    max_turns: int = 10

class EvalResultCase(BaseModel):
    task_id: str
    task_name: str
    category: str
    passed: bool
    score: float
    turns_used: int
    executed_tools: List[str]
    verification_details: List[str]
    failure_reasons: List[str]

class E2EEvalReport(BaseModel):
    total_tasks: int
    passed_tasks: int
    pass_rate: float
    category_scores: Dict[str, float]
    results: List[EvalResultCase]
