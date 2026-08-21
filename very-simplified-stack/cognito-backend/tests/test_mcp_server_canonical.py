import os
import json
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch
from pathlib import Path
from app.services.mcp_server import (
    mcp_server,
    mcp,
    execute_agent_task,
    get_session_status,
    load_mcp_config,
    verify_mcp_auth,
    cognito_architecture_context,
    cognito_task_status
)
from app.models.ai import AIResponse

@pytest.mark.asyncio
async def test_load_mcp_config_and_auth(tmp_path, monkeypatch):
    # Test default loading
    config = load_mcp_config()
    assert "Endpoint" in config
    assert "AuthToken" in config

    # Test ~/.cognito/config.json override
    fake_home = tmp_path / "home"
    fake_cognito = fake_home / ".cognito"
    fake_cognito.mkdir(parents=True)
    config_file = fake_cognito / "config.json"
    config_file.write_text(json.dumps({"AuthToken": "secret_token_123", "RequireAuth": True}))

    monkeypatch.setattr(Path, "home", lambda: fake_home)

    config_layered = load_mcp_config()
    assert config_layered["AuthToken"] == "secret_token_123"
    assert config_layered["RequireAuth"] is True

    # Test authentication verification
    assert verify_mcp_auth("secret_token_123") is True
    assert verify_mcp_auth("wrong_token") is False

@pytest.mark.asyncio
async def test_execute_agent_task_and_session_status():
    mock_ai_resp = AIResponse(response="Mocked response", metadata={"tokens": 10})
    with patch("app.services.reasoning_engine.reasoning_engine.process_request", new_callable=AsyncMock) as mock_proc:
        mock_proc.return_value = mock_ai_resp

        # Test execute_agent_task non-streaming mode
        res = await execute_agent_task(prompt="Test agent prompt", cwd="/tmp")
        assert res.get("status") == "completed"
        session_id = res.get("session_id")
        assert session_id is not None
        assert res.get("response") == "Mocked response"

        # Test get_session_status
        status_res = await get_session_status(session_id=session_id)
        assert status_res.get("session_id") == session_id
        assert status_res.get("status") == "active"
        assert "message_count" in status_res

@pytest.mark.asyncio
async def test_execute_agent_task_streaming():
    res = await execute_agent_task(prompt="Test prompt", cwd="/tmp", stream=True)
    assert res.get("status") == "streaming"
    assert res.get("sse_endpoint") == "/api/agent/loop"
    assert "session_id" in res

@pytest.mark.asyncio
async def test_mcp_recursion_and_wrapper():
    # Test recursion limit validation
    assert mcp_server.validate_recursion("codex", "corr-1", 1) is True
    assert mcp_server.validate_recursion("codex", "corr-1", 5) is False

    # Test call_tool with depth exceeding limit
    blocked_res = await mcp_server.call_tool(
        "cognito_architecture_context", {}, "codex", "corr-1", execution_depth=10
    )
    assert blocked_res.get("is_error") is True
    assert "Recursive execution depth limit exceeded" in blocked_res.get("output", "")

    # Test valid tool execution via call_tool
    valid_res = await mcp_server.call_tool(
        "cognito_architecture_context", {}, "codex", "corr-1", execution_depth=1
    )
    assert "architecture" in valid_res
