import json
import logging
import os
from typing import List, Dict, Any, Literal, Optional
from pydantic import BaseModel, Field
from app.models.domain import TaskContext
from app.services.ollama_client import ollama_client

logger = logging.getLogger("cognito.services.ollama_classifier")

class ClassificationResponse(BaseModel):
    task_type: str = Field(description="The category of task, e.g., explanation, rename, feature, bug_fix, refactor, auth_change, migration, destructive")
    complexity: Literal["low", "medium", "high"]
    risk: Literal["low", "medium", "high"]
    scope: Literal["single_file", "multi_file", "repository_wide"]
    ambiguity: Literal["clear", "moderate", "high"]
    required_capabilities: List[str] = Field(default_factory=list)
    expected_write_requirement: bool
    expected_network_requirement: bool
    probable_file_count: int
    recommended_logical_tier: Literal["local", "luna", "terra", "sol"]
    confidence: float
    reasons: List[str] = Field(default_factory=list)

DEFAULT_FALLBACK_CLASSIFICATION = ClassificationResponse(
    task_type="unknown",
    complexity="medium",
    risk="medium",
    scope="multi_file",
    ambiguity="moderate",
    required_capabilities=["coding"],
    expected_write_requirement=True,
    expected_network_requirement=False,
    probable_file_count=3,
    recommended_logical_tier="terra",
    confidence=0.5,
    reasons=["Ollama classifier fallback activated."]
)

class OllamaTaskClassifier:
    def __init__(self, model_override: Optional[str] = None):
        self.model_name = model_override or os.getenv("OLLAMA_MODEL_CLASSIFIER", "qwen3.5:9b")

    async def classify_task(self, context: TaskContext) -> ClassificationResponse:
        system_prompt = (
            "You are an AI software engineering task classifier.\n"
            "Your job is to analyze the user task and editor/repository context and return a valid JSON classification.\n"
            f"You MUST conform exactly to this JSON schema:\n"
            f"{json.dumps(ClassificationResponse.model_json_schema(), indent=2)}\n"
            "Return ONLY the raw JSON block. No markdown wrapper, no explanations."
        )

        user_prompt = (
            f"User Task: {context.user_task}\n\n"
            f"Language: {context.editor.selected_language or 'unknown'}\n"
            f"Active File: {context.editor.active_file or 'none'}\n"
            f"Diagnostics Summary: {json.dumps(context.editor.diagnostics_summary or {})}\n"
            f"Git Status Summary: {context.editor.git_status_summary or 'clean'}\n"
            f"Changed File Count: {context.repository.changed_files_count}\n"
            f"Repository Size Estimate: {context.repository.repository_size_estimate_kb or 'unknown'} KB\n"
            f"Detected Technologies: {', '.join(context.repository.detected_technologies)}\n"
            f"Sensitive Paths Indicators: {', '.join(context.sensitive_path_indicators)}\n"
            f"Test Framework Indicators: {', '.join(context.test_framework_indicators)}\n"
            f"Task History Indicators: {', '.join(context.task_history_indicators)}\n"
        )

        full_prompt = f"[SYSTEM]\n{system_prompt}\n\n[USER]\n{user_prompt}"

        try:
            # Send to Ollama requiring json format
            res = await ollama_client.generate(prompt=full_prompt, model_params={"format": "json", "temperature": 0.0})
            resp_text = res.get("response", "").strip()

            # Parse & validate
            return ClassificationResponse.model_validate_json(resp_text)
        except Exception as e:
            logger.warning(f"Ollama classification failed, falling back to default routing: {e}")
            return DEFAULT_FALLBACK_CLASSIFICATION

ollama_task_classifier = OllamaTaskClassifier()
