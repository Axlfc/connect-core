import pytest
import httpx
from typing import AsyncGenerator, Dict, Any

from app.core.retry import is_transient_error, retry_transient_stream
from app.services.backend_client import BackendClient
from app.services.backend_registry import BackendConfig, BackendType
from app.core.agent_loop import agent_loop
from app.core.tools.base import ToolContext
from app.core.events import TextDeltaEvent, ErrorEvent, DoneEvent


@pytest.mark.asyncio
async def test_is_transient_error():
    # 429 Rate Limit is transient
    res_429 = httpx.Response(429, request=httpx.Request("POST", "http://test"))
    err_429 = httpx.HTTPStatusError("Rate Limit", request=res_429.request, response=res_429)
    assert is_transient_error(err_429) is True

    # 503 Service Unavailable is transient
    res_503 = httpx.Response(503, request=httpx.Request("POST", "http://test"))
    err_503 = httpx.HTTPStatusError("Service Unavailable", request=res_503.request, response=res_503)
    assert is_transient_error(err_503) is True

    # 400 Bad Request is NOT transient
    res_400 = httpx.Response(400, request=httpx.Request("POST", "http://test"))
    err_400 = httpx.HTTPStatusError("Bad Request", request=res_400.request, response=res_400)
    assert is_transient_error(err_400) is False

    # Network / Timeout errors are transient
    assert is_transient_error(httpx.ConnectTimeout("Timeout")) is True
    assert is_transient_error(TimeoutError("Timeout")) is True


@pytest.mark.asyncio
async def test_retry_transient_stream_recovery():
    attempts = 0

    def transient_generator() -> AsyncGenerator[Dict[str, Any], None]:
        nonlocal attempts
        attempts += 1
        async def _gen():
            if attempts == 1:
                res_429 = httpx.Response(429, request=httpx.Request("POST", "http://test"))
                raise httpx.HTTPStatusError("429 Too Many Requests", request=res_429.request, response=res_429)
            yield {"token": "hello"}
            yield {"token": " world"}
        return _gen()

    chunks = []
    async for chunk in retry_transient_stream(transient_generator, max_attempts=3, min_wait=0.01, max_wait=0.05):
        chunks.append(chunk)

    assert attempts == 2
    assert len(chunks) == 2
    assert chunks[0]["token"] == "hello"
    assert chunks[1]["token"] == " world"


@pytest.mark.asyncio
async def test_retry_transient_stream_persistent_failure_explicit_error():
    attempts = 0

    def failing_generator() -> AsyncGenerator[Dict[str, Any], None]:
        nonlocal attempts
        attempts += 1
        async def _gen():
            res_500 = httpx.Response(500, request=httpx.Request("POST", "http://test"))
            raise httpx.HTTPStatusError("500 Internal Error", request=res_500.request, response=res_500)
            yield {}
        return _gen()

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        async for _ in retry_transient_stream(failing_generator, max_attempts=3, min_wait=0.01, max_wait=0.05):
            pass

    assert attempts == 3
    assert "500 Internal Error" in str(exc_info.value)


@pytest.mark.asyncio
async def test_retry_transient_stream_non_transient_no_retry():
    attempts = 0

    def non_transient_generator() -> AsyncGenerator[Dict[str, Any], None]:
        nonlocal attempts
        attempts += 1
        async def _gen():
            res_400 = httpx.Response(400, request=httpx.Request("POST", "http://test"))
            raise httpx.HTTPStatusError("400 Bad Request", request=res_400.request, response=res_400)
            yield {}
        return _gen()

    with pytest.raises(httpx.HTTPStatusError):
        async for _ in retry_transient_stream(non_transient_generator, max_attempts=3, min_wait=0.01, max_wait=0.05):
            pass

    # Should fail immediately on 1st attempt
    assert attempts == 1


@pytest.mark.asyncio
async def test_agent_loop_retry_and_explicit_error():
    class DummyRouter:
        def __init__(self):
            self.call_count = 0

        async def generate_with_tools(self, messages, tools_schema, model_params=None):
            self.call_count += 1
            res_429 = httpx.Response(429, request=httpx.Request("POST", "http://test"))
            raise httpx.HTTPStatusError("429 Too Many Requests", request=res_429.request, response=res_429)
            yield {}

    router = DummyRouter()
    context = ToolContext(session_id="test_session", cwd="/tmp", trusted=True, protected_files=[])

    events = []
    async for event in agent_loop(
        messages=[{"role": "user", "content": "hi"}],
        tools=[],
        context=context,
        backend_router=router,
    ):
        events.append(event)

    error_events = [e for e in events if isinstance(e, ErrorEvent)]
    done_events = [e for e in events if isinstance(e, DoneEvent)]

    assert len(error_events) == 1
    assert "No se pudo completar tras reintentos" in error_events[0].message
    assert "429 Too Many Requests" in error_events[0].message

    assert len(done_events) == 1
    assert done_events[0].stop_reason == "error"
