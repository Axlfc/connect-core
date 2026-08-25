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
    monkeypatch.delenv("COGNITO_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("COGNITO_API_KEY", raising=False)
    monkeypatch.delenv("COGNITO_MCP_INSECURE_DEV", raising=False)

    # Test default loading generate random token and require_auth True
    fake_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    config = load_mcp_config()
    assert "Endpoint" in config
    assert "AuthToken" in config
    assert len(config["AuthToken"]) > 0
    assert config["RequireAuth"] is True
    # Verify token was persisted to ~/.cognito/config.json
    config_file_persisted = fake_home / ".cognito" / "config.json"
    assert config_file_persisted.exists()
    persisted_data = json.loads(config_file_persisted.read_text(encoding="utf-8"))
    assert persisted_data.get("AuthToken") == config["AuthToken"]

    # Test ~/.cognito/config.json override
    fake_home = tmp_path / "home"
    fake_cognito = fake_home / ".cognito"
    fake_cognito.mkdir(parents=True, exist_ok=True)
    config_file = fake_cognito / "config.json"
    config_file.write_text(json.dumps({"AuthToken": "secret_token_123"}))

    monkeypatch.setattr(Path, "home", lambda: fake_home)

    config_layered = load_mcp_config()
    assert config_layered["AuthToken"] == "secret_token_123"
    assert config_layered["RequireAuth"] is True

    # Test authentication verification
    assert verify_mcp_auth("secret_token_123") is True
    assert verify_mcp_auth("wrong_token") is False
    assert verify_mcp_auth(None) is False

@pytest.mark.asyncio
async def test_mcp_unauthenticated_rejected_by_default(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    monkeypatch.delenv("COGNITO_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("COGNITO_API_KEY", raising=False)
    monkeypatch.delenv("COGNITO_MCP_INSECURE_DEV", raising=False)

    # Request without token must be rejected
    assert verify_mcp_auth() is False
    assert verify_mcp_auth("invalid_token") is False

    res = await execute_agent_task(prompt="Unauthorized prompt", cwd="/tmp")
    assert res.get("is_error") is True
    assert "Authentication failed" in res.get("output", "")

    status_res = await get_session_status(session_id="some-session")
    assert status_res.get("is_error") is True
    assert "Authentication failed" in status_res.get("output", "")

@pytest.mark.asyncio
async def test_load_mcp_config_persistence_failure_raises(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    monkeypatch.delenv("COGNITO_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("COGNITO_API_KEY", raising=False)
    monkeypatch.delenv("COGNITO_MCP_INSECURE_DEV", raising=False)

    with patch("builtins.open", side_effect=OSError("Disk full or permission denied")):
        with pytest.raises(RuntimeError, match="Failed to persist generated AuthToken"):
            load_mcp_config()

@pytest.mark.asyncio
async def test_mcp_insecure_dev_mode_opt_in(tmp_path, monkeypatch, caplog):
    fake_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    monkeypatch.delenv("COGNITO_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("COGNITO_API_KEY", raising=False)
    monkeypatch.setenv("COGNITO_MCP_INSECURE_DEV", "true")

    import logging
    with caplog.at_level(logging.WARNING):
        config = load_mcp_config()
        assert config["RequireAuth"] is False
        assert config["InsecureDev"] is True
        assert verify_mcp_auth() is True
        assert "INSECURE DEV MODE" in caplog.text

@pytest.mark.asyncio
async def test_execute_agent_task_and_session_status(monkeypatch):
    monkeypatch.setenv("COGNITO_AUTH_TOKEN", "valid_test_token")
    mock_ai_resp = AIResponse(response="Mocked response", metadata={"tokens": 10})
    with patch("app.services.reasoning_engine.reasoning_engine.process_request", new_callable=AsyncMock) as mock_proc:
        mock_proc.return_value = mock_ai_resp

        # Test execute_agent_task non-streaming mode with valid auth_token
        res = await execute_agent_task(prompt="Test agent prompt", cwd="/tmp", auth_token="valid_test_token")
        assert res.get("status") == "completed"
        session_id = res.get("session_id")
        assert session_id is not None
        assert res.get("response") == "Mocked response"

        # Test get_session_status with valid auth_token
        status_res = await get_session_status(session_id=session_id, auth_token="valid_test_token")
        assert status_res.get("session_id") == session_id
        assert status_res.get("status") == "active"
        assert "message_count" in status_res

@pytest.mark.asyncio
async def test_execute_agent_task_streaming(monkeypatch):
    monkeypatch.setenv("COGNITO_AUTH_TOKEN", "valid_test_token")
    res = await execute_agent_task(prompt="Test prompt", cwd="/tmp", stream=True, auth_token="valid_test_token")
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
