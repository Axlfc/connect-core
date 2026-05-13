"""
AGI Agents Module - Core reasoning and learning agents

This module implements the 5-phase AGI roadmap:
- Phase 1: Chain-of-Thought reasoning
- Phase 2: Self-evaluation and iteration
- Phase 3: Experience memory and learning
- Phase 4: Multi-agent collaboration
- Phase 5: Autonomous operation

All agents are designed to work within n8n Python runners.
"""

from .chain_of_thought_agent import ChainOfThoughtAgent
from .output_validator import OutputValidator
from .iterative_agent import IterativeAgent
from .model_router import ModelRouter
from .memory_manager import MemoryManager

__all__ = [
    "ChainOfThoughtAgent",
    "OutputValidator",
    "IterativeAgent",
    "ModelRouter",
    "MemoryManager",
]

__version__ = "1.0.0"
__author__ = "AGI Team"
