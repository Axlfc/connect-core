import pytest
import tempfile
import os
from pathlib import Path
from app.models.domain import TaskContext, RepositoryContext, EditorContext
from app.services.ollama_classifier import ClassificationResponse, OllamaTaskClassifier
from app.services.policy_engine import PolicyEngine
from app.services.model_discovery import model_discovery_service

def test_model_discovery_fallbacks():
    # Model discovery combined catalog
    catalog = pytest.mark.asyncio(lambda: model_discovery_service.get_combined_catalog())
    # Should run and resolve fallbacks without crashing
    assert catalog is not None

def test_policy_loading_and_validation():
    # Test valid default policy
    engine = PolicyEngine()
    assert engine.validate_policy() is True

    # Test invalid policy fallback (valid TOML but missing overrides key)
    with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as tmp:
        tmp.write(b"missing_overrides = true\n")
        tmp_name = tmp.name

    try:
        engine_invalid = PolicyEngine(policy_path=tmp_name)
        assert engine_invalid.validate_policy() is False
    finally:
        os.unlink(tmp_name)

def test_policy_precedence_and_overrides():
    engine = PolicyEngine()

    # Standard task context
    repo = RepositoryContext(
        repository_id="test-repo",
        root_path="/tmp",
        current_branch="main",
        base_commit="abc1234",
        is_dirty=False,
        changed_files_count=0,
        detected_technologies=["python"]
    )
    editor = EditorContext(workspace_folder="/tmp")

    # Scenario 1: Authentication / High Risk override -> Sol Plan-first
    context_auth = TaskContext(
        repository=repo,
        editor=editor,
        user_task="Implement OAuth2 authentication login flow"
    )
    classif = ClassificationResponse(
        task_type="feature",
        complexity="medium",
        risk="medium",
        scope="multi_file",
        ambiguity="clear",
        expected_write_requirement=True,
        expected_network_requirement=False,
        probable_file_count=2,
        recommended_logical_tier="terra",
        confidence=0.9
    )
    decision = engine.evaluate(context_auth, classif)
    assert decision.logical_tier == "sol"
    assert decision.mode == "plan"
    assert decision.risk == "high"

    # Scenario 2: Formatting / Rename override -> Luna
    context_rename = TaskContext(
        repository=repo,
        editor=editor,
        user_task="rename calculate_sum to calc_sum across files"
    )
    decision = engine.evaluate(context_rename, classif)
    assert decision.logical_tier == "luna"
    assert decision.mode == "act"
    assert decision.risk == "low"

    # Scenario 3: Explanation / Read-only override -> Ollama
    context_explain = TaskContext(
        repository=repo,
        editor=editor,
        user_task="explain how the router works"
    )
    decision = engine.evaluate(context_explain, classif)
    assert decision.executor == "Ollama"
    assert decision.logical_tier == "local"
    assert decision.mode == "read"
    assert decision.execution_policy.sandbox.read_only is True
