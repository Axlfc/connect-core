"""
Unit tests for AGI agents.
Run with: python -m pytest tests/
"""

import pytest
import json
from chain_of_thought_agent import ChainOfThoughtAgent
from output_validator import OutputValidator
from iterative_agent import IterativeAgent
from model_router import ModelRouter


class TestChainOfThoughtAgent:
    """Test Chain-of-Thought reasoning."""

    def test_basic_cot(self):
        """Test basic CoT execution."""
        agent = ChainOfThoughtAgent()
        # Note: This test requires Ollama running
        # In CI, use mocking instead
        # result = agent.solve("What is 2+2?")
        # assert result["success"] is True
        # assert len(result["reasoning_chain"]) == 5

    def test_reasoning_chain_structure(self):
        """Test that reasoning chain has expected structure."""
        agent = ChainOfThoughtAgent()
        # Test data
        agent.analyze_task("Test task")
        # Would need mock Ollama for full test


class TestOutputValidator:
    """Test output validation."""

    def test_validator_initialization(self):
        """Test validator setup."""
        validator = OutputValidator()
        assert validator.model == "qwen2.5-coder"
        assert validator.overall_score == 0

    def test_extract_rating(self):
        """Test rating extraction from text."""
        validator = OutputValidator()
        
        # Test rating extraction
        test_text = "5 This is excellent work because it covers all aspects"
        rating = validator._extract_rating(test_text)
        assert rating == 5
        
        test_text2 = "Rating: 2 out of 5, needs improvement"
        rating2 = validator._extract_rating(test_text2)
        assert rating2 == 2


class TestModelRouter:
    """Test model routing."""

    def test_router_initialization(self):
        """Test router setup."""
        router = ModelRouter()
        assert len(router.classification_history) == 0
        assert len(router.routing_history) == 0

    def test_model_selection(self):
        """Test model selection logic."""
        router = ModelRouter()
        
        # Test selection for known categories
        model_code = router.select_model("coding")
        assert model_code in ["qwen2.5-coder", "deepseek-r1"]
        
        model_creative = router.select_model("creative")
        assert model_creative in ["llama3.2", "qwen2.5-coder"]
        
        # Test default for unknown category
        model_default = router.select_model("unknown")
        assert model_default == "qwen2.5-coder"

    def test_routing_stats(self):
        """Test routing statistics."""
        router = ModelRouter()
        stats = router.get_routing_stats()
        assert stats["total_tasks"] == 0
        assert "categories_used" in stats
        assert "models_used" in stats


class TestIntegration:
    """Integration tests combining multiple agents."""

    def test_iterative_agent_concept(self):
        """Test iterative agent logic (without Ollama)."""
        # Would need proper mocking of Ollama for full test
        agent = IterativeAgent(quality_threshold=3.5, max_iterations=3)
        assert agent.quality_threshold == 3.5
        assert agent.max_iterations == 3


if __name__ == "__main__":
    # Run tests with: python -m pytest tests/test_agents.py -v
    pytest.main([__file__, "-v"])
