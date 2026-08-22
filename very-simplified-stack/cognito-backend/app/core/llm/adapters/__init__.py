"""
LLM Adapters package.
"""
from app.core.llm.adapters.base import (
    LLMAdapter,
    LLMError,
    LLMRetryableError,
    LLMNonRetryableError,
    is_retryable_http_status,
)
from app.core.llm.adapters.ollama import OllamaAdapter
from app.core.llm.adapters.openai_compatible import OpenAICompatibleAdapter

__all__ = [
    "LLMAdapter",
    "LLMError",
    "LLMRetryableError",
    "LLMNonRetryableError",
    "is_retryable_http_status",
    "OllamaAdapter",
    "OpenAICompatibleAdapter",
]
