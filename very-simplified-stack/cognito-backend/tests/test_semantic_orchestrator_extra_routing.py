import pytest
from app.services.semantic_orchestrator import SemanticOrchestrator
from app.services.backend_registry import BACKENDS_BY_PRIORITY

def test_semantic_orchestrator_default_routing():
    # extra_routing=None should use MODEL_ROUTING
    orchestrator = SemanticOrchestrator(configs=BACKENDS_BY_PRIORITY)
    from app.services.semantic_orchestrator import MODEL_ROUTING
    assert orchestrator.routing == MODEL_ROUTING

def test_semantic_orchestrator_extra_routing():
    extra = {"my_intent": {"backend": "b1", "model": "m1"}}
    orchestrator = SemanticOrchestrator(configs=BACKENDS_BY_PRIORITY, extra_routing=extra)

    assert orchestrator.routing["my_intent"] == extra["my_intent"]
    # Should still have default ones
    assert "general" in orchestrator.routing

def test_add_intent_route():
    orchestrator = SemanticOrchestrator(configs=BACKENDS_BY_PRIORITY)
    orchestrator.add_intent_route("dynamic", "ext_backend", "ext_model")

    assert orchestrator.routing["dynamic"] == {"backend": "ext_backend", "model": "ext_model"}
