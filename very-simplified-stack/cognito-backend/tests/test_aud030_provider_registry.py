import pytest
import respx
from httpx import Response

from app.core.llm.adapters.base import LLMAdapter, register_provider, PROVIDER_REGISTRY
from app.core.llm.adapters.anthropic import AnthropicAdapter
from app.core.llm.config import AdapterConfig, RouterConfig, RouteConfig
from app.core.llm.router import create_adapter_from_config, LLMRouter


def test_provider_registration_and_lookup():
    """Verify that adapters registered with @register_provider are stored in PROVIDER_REGISTRY."""
    assert "ollama" in PROVIDER_REGISTRY
    assert "openai" in PROVIDER_REGISTRY
    assert "anthropic" in PROVIDER_REGISTRY
    assert "claude" in PROVIDER_REGISTRY


@pytest.mark.asyncio
@respx.mock
async def test_anthropic_adapter_chat_completion():
    """Test AnthropicAdapter chat completion parsing and headers."""
    route = respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=Response(
            200,
            json={
                "id": "msg_123",
                "type": "message",
                "role": "assistant",
                "model": "claude-3-5-sonnet-20241022",
                "content": [{"type": "text", "text": "Hello from Claude!"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
        )
    )

    adapter = AnthropicAdapter(
        model_name="claude-3-5-sonnet-20241022",
        base_url="https://api.anthropic.com",
        api_key="test-key",
    )

    resp = await adapter.chat_completion(
        messages=[{"role": "user", "content": "Hi"}],
        temperature=0.5,
    )

    assert resp["id"] == "msg_123"
    assert resp["choices"][0]["message"]["content"] == "Hello from Claude!"
    assert resp["usage"]["prompt_tokens"] == 10
    assert resp["usage"]["completion_tokens"] == 5

    assert route.called
    req = route.calls.last.request
    assert req.headers["x-api-key"] == "test-key"
    assert req.headers["anthropic-version"] == "2023-06-01"


def test_dynamic_provider_dispatch_without_modifying_router():
    """
    Demonstrates acceptance criterion for AUD-030:
    A custom provider adapter registered dynamically can be instantiated and dispatched by LLMRouter
    via config without modifying router.py logic.
    """
    @register_provider("custom_test_provider")
    class CustomTestAdapter(LLMAdapter):
        async def _do_chat_completion(self, messages, temperature=0.7, max_tokens=None, **kwargs):
            return {
                "id": "custom-1",
                "choices": [{"message": {"role": "assistant", "content": "Custom response"}}],
            }

        async def _do_stream_completion(self, messages, temperature=0.7, max_tokens=None, **kwargs):
            yield {"choices": [{"delta": {"content": "Custom stream"}}]}

    # Build config referencing the new custom provider type
    config = RouterConfig(
        adapters=[
            AdapterConfig(
                id="custom_adapter",
                type="custom_test_provider",
                model_name="custom-model-v1",
                base_url="http://localhost:9999",
            )
        ],
        routes={
            "custom_route": RouteConfig(
                primary_adapter_id="custom_adapter",
                fallback_adapter_ids=[],
            )
        },
    )

    router = LLMRouter()
    router.load_from_config(config)

    adapter_instance = router.get_adapter("custom_adapter")
    assert adapter_instance is not None
    assert isinstance(adapter_instance, CustomTestAdapter)
    assert adapter_instance.model_name == "custom-model-v1"
