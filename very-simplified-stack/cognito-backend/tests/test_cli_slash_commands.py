import pytest
import tempfile
import os
import sys
import io
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

from cli.slash_commands import handle_slash_command
from cli.cognito_cli import interactive_loop
from cli.config import CognitoConfig
from app.core.project_trust import ProjectTrustStore
from app.core.session_manager import SessionManager

@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as tmp:
        yield tmp

@pytest.mark.asyncio
async def test_slash_clear(capsys, tmp_dir):
    handled, sess_id = await handle_slash_command("/clear", cwd=tmp_dir, current_session_id="s123")
    assert handled is True
    assert sess_id == "s123"

    out, err = capsys.readouterr()
    assert "\033[H\033[2J" in out
    assert "[Pantalla y contexto visual limpiados]" in out

@pytest.mark.asyncio
async def test_slash_status(capsys, tmp_dir):
    handled, sess_id = await handle_slash_command("/status", cwd=tmp_dir, current_session_id="sess_abc")
    assert handled is True
    assert sess_id == "sess_abc"

    out, err = capsys.readouterr()
    assert "=== Cognito Status ===" in out
    assert "Session ID: sess_abc" in out
    assert f"CWD: {tmp_dir}" in out
    assert "Trusted:" in out

@pytest.mark.asyncio
async def test_slash_trust(capsys, tmp_dir, monkeypatch):
    trust_file = os.path.join(tmp_dir, "trust.json")

    # Patch ProjectTrustStore store_path
    with patch.object(ProjectTrustStore, "__init__", lambda self: setattr(self, "store_path", Path(trust_file)) or setattr(self, "exec_policy", MagicMock()) or self._ensure_dir()):
        # Initially False
        handled, _ = await handle_slash_command("/trust", cwd=tmp_dir)
        assert handled is True
        out, _ = capsys.readouterr()
        assert "trusted=True" in out

        # Toggle back to False
        handled, _ = await handle_slash_command("/trust", cwd=tmp_dir)
        assert handled is True
        out, _ = capsys.readouterr()
        assert "trusted=False" in out

        # Explicit on
        handled, _ = await handle_slash_command("/trust on", cwd=tmp_dir)
        assert handled is True
        out, _ = capsys.readouterr()
        assert "trusted=True" in out

        # Explicit off
        handled, _ = await handle_slash_command("/trust off", cwd=tmp_dir)
        assert handled is True
        out, _ = capsys.readouterr()
        assert "trusted=False" in out

@pytest.mark.asyncio
async def test_slash_compact_no_session(capsys, tmp_dir):
    handled, _ = await handle_slash_command("/compact", cwd=tmp_dir, current_session_id=None)
    assert handled is True
    out, _ = capsys.readouterr()
    assert "[Advertencia: No hay sesión activa para compactar.]" in out

@pytest.mark.asyncio
async def test_slash_compact_with_session(capsys, tmp_dir, monkeypatch):
    # Setup session manager with dummy session
    session_manager = SessionManager(sessions_dir=Path(tmp_dir))
    sess_id = session_manager.create(cwd=tmp_dir)
    session_manager.append_message(sess_id, "user", "Hello world")
    session_manager.append_message(sess_id, "assistant", "Hi there")

    monkeypatch.setattr("cli.slash_commands.SessionManager", lambda: session_manager)
    monkeypatch.setattr("cli.slash_commands.compact", AsyncMock(return_value="Resumen de prueba"))

    handled, res_sess = await handle_slash_command("/compact", cwd=tmp_dir, current_session_id=sess_id)
    assert handled is True
    assert res_sess == sess_id

    out, _ = capsys.readouterr()
    assert f"[Sesión {sess_id} compactada exitosamente.]" in out

    # Verify compaction appended
    messages = session_manager.get_effective_messages(sess_id)
    assert len(messages) == 1
    assert messages[0]["role"] == "system"
    assert "Resumen de prueba" in messages[0]["content"]

@pytest.mark.asyncio
async def test_unknown_slash_command(capsys, tmp_dir):
    handled, _ = await handle_slash_command("/foobar", cwd=tmp_dir)
    assert handled is True
    out, _ = capsys.readouterr()
    assert "[Comando no reconocido: /foobar." in out

@pytest.mark.asyncio
async def test_non_slash_command(tmp_dir):
    handled, _ = await handle_slash_command("Hola cognito", cwd=tmp_dir)
    assert handled is False

@pytest.mark.asyncio
async def test_interactive_loop(tmp_dir, capsys, monkeypatch):
    prompts = ["/status", "hello prompt", "/exit"]
    prompt_index = 0

    async def mock_prompt_async(self, prompt=""):
        nonlocal prompt_index
        if prompt_index < len(prompts):
            val = prompts[prompt_index]
            prompt_index += 1
            return val
        raise EOFError()

    monkeypatch.setattr("prompt_toolkit.PromptSession.prompt_async", mock_prompt_async)

    # Mock CognitoClient
    client = MagicMock()
    async def mock_agent_loop(messages, cwd, session_id=None):
        yield {"type": "session_info", "session_id": "sess_interactive", "is_new": True}
        yield {"type": "text_delta", "content": "Response delta"}
        yield {"type": "done", "stop_reason": "end_turn"}

    client.agent_loop = mock_agent_loop
    config = MagicMock(spec=CognitoConfig)
    config.no_color = True

    code = await interactive_loop(client, config, cwd=tmp_dir, session_id=None)
    assert code == 0

    out, err = capsys.readouterr()
    assert "Cognito CLI - Modo Interactivo" in out
    assert "=== Cognito Status ===" in out
    assert "Response delta" in out
