"""
Integration test - smoke test for agents
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chain_of_thought_agent import ChainOfThoughtAgent
from output_validator import OutputValidator
from model_router import ModelRouter


def test_imports():
    """Test that all agent modules can be imported."""
    print("✓ All agent modules imported successfully")


def test_agent_initialization():
    """Test basic initialization of agents."""
    cot = ChainOfThoughtAgent()
    print(f"✓ ChainOfThoughtAgent initialized (model: {cot.model})")

    validator = OutputValidator()
    print(f"✓ OutputValidator initialized (model: {validator.model})")

    router = ModelRouter()
    print(f"✓ ModelRouter initialized")

    print("\nAll agents initialized successfully!")


if __name__ == "__main__":
    test_imports()
    test_agent_initialization()
    print("\n✅ Smoke tests passed!")
