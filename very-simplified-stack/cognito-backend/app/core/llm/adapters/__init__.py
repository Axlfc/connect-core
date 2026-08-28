"""
LLM Adapters package.
"""
from app.core.llm.adapters.base import (
    LLMAdapter,
    LLMProviderAdapter,
    LLMError,
    LLMRetryableError,
    LLMNonRetryableError,
    is_retryable_http_status,
    register_provider,
    get_provider_class,
    PROVIDER_REGISTRY,
)
from app.core.llm.adapters.ollama import OllamaAdapter
from app.core.llm.adapters.openai_compatible import OpenAICompatibleAdapter
from app.core.llm.adapters.anthropic import AnthropicAdapter

__all__ = [
    "LLMAdapter",
    "LLMProviderAdapter",
    "LLMError",
    "LLMRetryableError",
    "LLMNonRetryableError",
    "is_retryable_http_status",
    "register_provider",
    "get_provider_class",
    "PROVIDER_REGISTRY",
    "OllamaAdapter",
    "OpenAICompatibleAdapter",
    "AnthropicAdapter",
]
