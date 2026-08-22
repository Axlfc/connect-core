import json
import pytest
import respx
import httpx
from pathlib import Path

from app.core.llm.router import LLMRouter
from app.core.llm.adapters.ollama import OllamaAdapter
from app.core.llm.adapters.openai_compatible import OpenAICompatibleAdapter
from app.core.llm.adapters.base import LLMError


@pytest.mark.asyncio
async def test_router_primary_adapter_success(respx_mock):
    respx_mock.post("https://api.deepseek.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [{"message": {"role": "assistant", "content": "Primary Success"}}],
            },
        )
    )

    router = LLMRouter()
    primary = OpenAICompatibleAdapter(
        model_name="deepseek-coder",
        base_url="https://api.deepseek.com/v1",
        api_key="sk-test",
    )
    router.register_adapter("deepseek-primary", primary)
    router.register_route("coder", primary_adapter_id="deepseek-primary")

    response = await router.chat_completion("coder", messages=[{"role": "user", "content": "Write code"}])
    assert response["choices"][0]["message"]["content"] == "Primary Success"


@pytest.mark.asyncio
async def test_router_fallback_when_primary_fails(respx_mock):
    # Primary (DeepSeek) fails with 500 continuously
    respx_mock.post("https://api.deepseek.com/v1/chat/completions").mock(
        return_value=httpx.Response(500, text="Internal Server Error")
    )
    # Secondary (Ollama local) succeeds
    respx_mock.post("http://localhost:11434/api/chat").mock(
        return_value=httpx.Response(
            200,
            json={
                "message": {"role": "assistant", "content": "Fallback Ollama Success"},
                "done": True,
            },
        )
    )

    router = LLMRouter()
    primary = OpenAICompatibleAdapter(
        model_name="deepseek-r1",
        base_url="https://api.deepseek.com/v1",
        max_retries=1,
        initial_backoff=0.01,
    )
    fallback = OllamaAdapter(
        model_name="llama3.2:1b",
        base_url="http://localhost:11434",
    )

    router.register_adapter("primary-deepseek", primary)
    router.register_adapter("fallback-ollama", fallback)
    router.register_route("smart-coder", primary_adapter_id="primary-deepseek", fallback_adapter_ids=["fallback-ollama"])

    response = await router.chat_completion("smart-coder", messages=[{"role": "user", "content": "Solve math"}])
    assert response["choices"][0]["message"]["content"] == "Fallback Ollama Success"


@pytest.mark.asyncio
async def test_router_all_adapters_fail_raises_llm_error(respx_mock):
    respx_mock.post("https://api.deepseek.com/v1/chat/completions").mock(
        return_value=httpx.Response(500, text="DeepSeek Down")
    )
    respx_mock.post("http://localhost:11434/api/chat").mock(
        return_value=httpx.Response(500, text="Ollama Down")
    )

    router = LLMRouter()
    primary = OpenAICompatibleAdapter(
        model_name="deepseek-r1",
        base_url="https://api.deepseek.com/v1",
        max_retries=0,
    )
    fallback = OllamaAdapter(
        model_name="llama3.2:1b",
        base_url="http://localhost:11434",
        max_retries=0,
    )

    router.register_adapter("p1", primary)
    router.register_adapter("f1", fallback)
    router.register_route("route1", primary_adapter_id="p1", fallback_adapter_ids=["f1"])

    with pytest.raises(LLMError) as exc_info:
        await router.chat_completion("route1", messages=[{"role": "user", "content": "Hello"}])

    assert "All adapters in route 'route1' failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_router_load_from_pathlib_config(tmp_path: Path, respx_mock):
    config_file = tmp_path / "router_config.json"
    config_data = {
        "adapters": [
            {
                "id": "ollama-local",
                "type": "ollama",
                "model_name": "qwen2.5:7b",
                "base_url": "http://localhost:11434",
                "max_retries": 2,
                "initial_backoff": 0.01
            },
            {
                "id": "openrouter-cloud",
                "type": "openai_compatible",
                "model_name": "meta-llama/llama-3.3-70b-instruct",
                "base_url": "https://openrouter.ai/api/v1",
                "api_key": "sk-or-test",
                "max_retries": 2,
                "initial_backoff": 0.01
            }
        ],
        "routes": {
            "default_chat": {
                "primary_adapter_id": "openrouter-cloud",
                "fallback_adapter_ids": ["ollama-local"]
            }
        }
    }
    config_file.write_text(json.dumps(config_data), encoding="utf-8")

    respx_mock.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [{"message": {"role": "assistant", "content": "OpenRouter Result"}}],
            },
        )
    )

    router = LLMRouter()
    router.load_from_file(config_file)

    adapter = router.get_adapter("ollama-local")
    assert adapter is not None
    assert adapter.model_name == "qwen2.5:7b"

    response = await router.chat_completion("default_chat", messages=[{"role": "user", "content": "Hi"}])
    assert response["choices"][0]["message"]["content"] == "OpenRouter Result"
