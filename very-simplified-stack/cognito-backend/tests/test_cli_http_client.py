import pytest
import json
import httpx
from cli.http_client import CognitoClient

@pytest.mark.asyncio
async def test_client_agent_loop(respx_mock):
    # respx is great for mocking httpx
    # If not available, we can mock the client itself, but let's try to mock the network

    endpoint = "http://localhost:8000"
    sse_content = (
        "data: {\"type\": \"session_info\", \"session_id\": \"s1\", \"is_new\": true}\n\n"
        "data: {\"type\": \"text_delta\", \"content\": \"Hello\"}\n\n"
        "data: {\"type\": \"done\", \"stop_reason\": \"end_turn\"}\n\n"
    )

    respx_mock.post(f"{endpoint}/api/agent/loop").return_value = httpx.Response(
        200,
        content=sse_content,
        headers={"Content-Type": "text/event-stream"}
    )

    async with CognitoClient(endpoint) as client:
        events = []
        async for event in client.agent_loop(messages=[], cwd="/tmp"):
            events.append(event)

    assert len(events) == 3
    assert events[0]["type"] == "session_info"
    assert events[1]["content"] == "Hello"

@pytest.mark.asyncio
async def test_client_sessions(respx_mock):
    endpoint = "http://localhost:8000"
    respx_mock.get(f"{endpoint}/api/agent/sessions").return_value = httpx.Response(200, json=[{"session_id": "s1"}])

    async with CognitoClient(endpoint) as client:
        sessions = await client.list_sessions()

    assert len(sessions) == 1
    assert sessions[0]["session_id"] == "s1"
