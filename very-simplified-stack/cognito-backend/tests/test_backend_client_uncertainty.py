import pytest
import json
import httpx
from unittest.mock import AsyncMock, MagicMock
from app.services.backend_client import BackendClient
from app.services.backend_registry import BackendConfig, BackendType

@pytest.mark.asyncio
async def test_generate_with_uncertainty_ollama(respx_mock):
    config = BackendConfig(
        name="test-ollama",
        base_url="http://ollama:11434",
        backend_type=BackendType.OLLAMA,
        model="test-model",
        priority=1
    )
    client = BackendClient(config)

    # Mock stream response for /api/generate (Ollama native)
    # Logprobs must have multiple candidates to result in non-zero uncertainty
    sse_lines = [
        json.dumps({
            "response": "Hello",
            "done": False,
            "logprobs": [{
                "top_logprobs": [
                    {"token": "Hello", "logprob": -0.1},
                    {"token": "Hi", "logprob": -1.5}
                ]
            }]
        }),
        json.dumps({
            "response": " world",
            "done": True,
            "logprobs": [{
                "top_logprobs": [
                    {"token": " world", "logprob": -0.2},
                    {"token": " earth", "logprob": -1.2}
                ]
            }]
        })
    ]
    respx_mock.post("http://ollama:11434/api/generate").return_value = httpx.Response(
        200, content="\n".join(sse_lines) + "\n"
    )

    text, uncertainty = await client.generate_with_uncertainty("test prompt")

    assert text == "Hello world"
    assert uncertainty is not None
    assert uncertainty > 0

@pytest.mark.asyncio
async def test_generate_with_uncertainty_no_logprobs(respx_mock):
    config = BackendConfig(
        name="test-openai",
        base_url="http://openai:8000",
        backend_type=BackendType.OPENAI,
        model="test-model",
        priority=1
    )
    client = BackendClient(config)

    # OpenAI style stream
    sse_content = (
        "data: {\"choices\": [{\"delta\": {\"content\": \"Hello\"}}]}\n\n"
        "data: [DONE]\n\n"
    )
    respx_mock.post("http://openai:8000/v1/chat/completions").return_value = httpx.Response(
        200, content=sse_content
    )

    text, uncertainty = await client.generate_with_uncertainty("test prompt")

    assert text == "Hello"
    assert uncertainty is None
