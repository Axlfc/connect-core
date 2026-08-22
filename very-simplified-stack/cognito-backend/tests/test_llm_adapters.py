import pytest
import respx
import httpx
from app.core.llm.adapters.base import LLMRetryableError, LLMNonRetryableError
from app.core.llm.adapters.ollama import OllamaAdapter
from app.core.llm.adapters.openai_compatible import OpenAICompatibleAdapter


@pytest.mark.asyncio
async def test_ollama_adapter_chat_success(respx_mock):
    respx_mock.post("http://localhost:11434/api/chat").mock(
        return_value=httpx.Response(
            200,
            json={
                "created_at": "2025-01-01T00:00:00Z",
                "message": {"role": "assistant", "content": "Hello from Ollama"},
                "done": True,
                "prompt_eval_count": 10,
                "eval_count": 5,
            },
        )
    )

    adapter = OllamaAdapter(model_name="llama3", base_url="http://localhost:11434")
    response = await adapter.chat_completion(messages=[{"role": "user", "content": "Hi"}])

    assert response["model"] == "llama3"
    assert response["choices"][0]["message"]["content"] == "Hello from Ollama"
    assert response["usage"]["total_tokens"] == 15


@pytest.mark.asyncio
async def test_ollama_adapter_retry_503_and_succeed(respx_mock):
    route = respx_mock.post("http://localhost:11434/api/chat")
    route.side_effect = [
        httpx.Response(503, text="Service Unavailable"),
        httpx.Response(
            200,
            json={
                "created_at": "2025-01-01T00:00:00Z",
                "message": {"role": "assistant", "content": "Recovered from 503"},
                "done": True,
                "prompt_eval_count": 5,
                "eval_count": 5,
            },
        ),
    ]

    adapter = OllamaAdapter(
        model_name="llama3",
        base_url="http://localhost:11434",
        max_retries=2,
        initial_backoff=0.01,
        backoff_factor=1.0,
    )
    response = await adapter.chat_completion(messages=[{"role": "user", "content": "Hi"}])

    assert response["choices"][0]["message"]["content"] == "Recovered from 503"
    assert route.call_count == 2


@pytest.mark.asyncio
async def test_ollama_adapter_fast_fail_400(respx_mock):
    route = respx_mock.post("http://localhost:11434/api/chat").mock(
        return_value=httpx.Response(400, text="Bad Request Format")
    )

    adapter = OllamaAdapter(
        model_name="llama3",
        base_url="http://localhost:11434",
        max_retries=3,
        initial_backoff=0.01,
    )

    with pytest.raises(LLMNonRetryableError) as exc_info:
        await adapter.chat_completion(messages=[{"role": "user", "content": "Hi"}])

    assert "Bad Request Format" in str(exc_info.value)
    # Should fail fast without retrying 3 times
    assert route.call_count == 1


@pytest.mark.asyncio
async def test_openai_adapter_chat_success(respx_mock):
    respx_mock.post("https://api.deepseek.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "chatcmpl-123",
                "object": "chat.completion",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Hello from DeepSeek"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 8, "completion_tokens": 4, "total_tokens": 12},
            },
        )
    )

    adapter = OpenAICompatibleAdapter(
        model_name="deepseek-chat",
        base_url="https://api.deepseek.com/v1",
        api_key="sk-test",
    )
    response = await adapter.chat_completion(messages=[{"role": "user", "content": "Hi"}])

    assert response["choices"][0]["message"]["content"] == "Hello from DeepSeek"


@pytest.mark.asyncio
async def test_openai_adapter_stream_success(respx_mock):
    sse_data = (
        "data: {\"choices\": [{\"delta\": {\"content\": \"Hello \"}}]}\n\n"
        "data: {\"choices\": [{\"delta\": {\"content\": \"world!\"}}]}\n\n"
        "data: [DONE]\n\n"
    )
    respx_mock.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(200, text=sse_data)
    )

    adapter = OpenAICompatibleAdapter(
        model_name="gpt-4o",
        base_url="https://api.openai.com/v1",
        api_key="sk-test",
    )

    chunks = []
    async for chunk in adapter.stream_completion(messages=[{"role": "user", "content": "Hi"}]):
        chunks.append(chunk)

    assert len(chunks) == 2
    assert chunks[0]["choices"][0]["delta"]["content"] == "Hello "
    assert chunks[1]["choices"][0]["delta"]["content"] == "world!"


@pytest.mark.asyncio
async def test_openai_adapter_fast_fail_401(respx_mock):
    route = respx_mock.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(401, text="Unauthorized: Invalid API Key")
    )

    adapter = OpenAICompatibleAdapter(
        model_name="gpt-4o",
        base_url="https://api.openai.com/v1",
        api_key="sk-invalid",
        max_retries=3,
        initial_backoff=0.01,
    )

    with pytest.raises(LLMNonRetryableError) as exc_info:
        await adapter.chat_completion(messages=[{"role": "user", "content": "Hi"}])

    assert "Unauthorized" in str(exc_info.value)
    assert route.call_count == 1
