import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.semantic_orchestrator import SemanticOrchestrator, SubTask, RoutingPlan
from app.services.backend_registry import BackendConfig, BackendType
from app.models.ai import AIRequest

@pytest.fixture
def mock_configs():
    return [
        BackendConfig(name="ollama-local", base_url="http://local", backend_type=BackendType.OLLAMA, model="m1", priority=1),
    ]

@pytest.mark.asyncio
async def test_escalation_logic(mock_configs, monkeypatch):
    orchestrator = SemanticOrchestrator(configs=mock_configs)

    # Mock task and prompt
    task = SubTask(id="1", description="desc", intent="general", input_slice="input", depends_on=[])
    prompt = "input"

    # Mock escalation routing
    monkeypatch.setattr("app.services.semantic_orchestrator.ESCALATION_ROUTING", {
        "general": {"backend": "ollama-local", "model": "phi4:latest"}
    })
    monkeypatch.setattr("app.services.semantic_orchestrator.ESCALATION_THRESHOLD", 0.5)
    monkeypatch.setattr("app.services.semantic_orchestrator.ESCALATION_ENABLED", True)

    # First attempt: high uncertainty (0.8)
    # Second attempt: low uncertainty (0.2)
    with patch("app.services.backend_client.BackendClient.generate_with_uncertainty") as mock_gen:
        mock_gen.side_effect = [
            ("Low quality response", 0.8),
            ("High quality response", 0.2)
        ]

        text, final_backend, final_model, escalated = await orchestrator._execute_subtask_with_escalation(
            task, "general", "ollama-local", "m1", prompt
        )

        assert escalated is True
        assert text == "High quality response"
        assert final_model == "phi4:latest"
        assert mock_gen.call_count == 2

@pytest.mark.asyncio
async def test_no_escalation_when_disabled(mock_configs, monkeypatch):
    orchestrator = SemanticOrchestrator(configs=mock_configs)
    task = SubTask(id="1", description="desc", intent="general", input_slice="input", depends_on=[])

    monkeypatch.setattr("app.services.semantic_orchestrator.ESCALATION_ENABLED", False)

    with patch("app.services.backend_client.BackendClient.generate") as mock_gen:
        mock_gen.return_value = {"response": "normal response"}

        text, _, _, escalated = await orchestrator._execute_subtask_with_escalation(
            task, "general", "ollama-local", "m1", "prompt"
        )

        assert escalated is False
        assert text == "normal response"
        mock_gen.assert_called_once()

@pytest.mark.asyncio
async def test_no_escalation_for_unmapped_intent(mock_configs, monkeypatch):
    orchestrator = SemanticOrchestrator(configs=mock_configs)
    task = SubTask(id="1", description="desc", intent="vision", input_slice="input", depends_on=[])

    monkeypatch.setattr("app.services.semantic_orchestrator.ESCALATION_ROUTING", {})
    monkeypatch.setattr("app.services.semantic_orchestrator.ESCALATION_THRESHOLD", 0.5)

    with patch("app.services.backend_client.BackendClient.generate_with_uncertainty") as mock_gen:
        mock_gen.return_value = ("uncertain but unmapped", 0.9)

        text, _, _, escalated = await orchestrator._execute_subtask_with_escalation(
            task, "vision", "ollama-local", "m1", "prompt"
        )

        assert escalated is False
        assert text == "uncertain but unmapped"
        assert mock_gen.call_count == 1
