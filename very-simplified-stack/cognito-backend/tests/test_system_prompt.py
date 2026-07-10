import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from app.core.system_prompt import build_system_message, COGNITO_SYSTEM_PROMPT
from app.api.routes.ai_agents import AgentLoopRequest, run_agent_loop
from app.core.session_manager import SessionManager

def test_build_system_message_absent():
    with tempfile.TemporaryDirectory() as tmpdir:
        msg = build_system_message(tmpdir)
        assert msg == COGNITO_SYSTEM_PROMPT

def test_build_system_message_empty():
    with tempfile.TemporaryDirectory() as tmpdir:
        agents_md_path = Path(tmpdir) / "AGENTS.md"
        agents_md_path.write_text("")
        msg = build_system_message(tmpdir)
        assert msg == COGNITO_SYSTEM_PROMPT

def test_build_system_message_whitespace():
    with tempfile.TemporaryDirectory() as tmpdir:
        agents_md_path = Path(tmpdir) / "AGENTS.md"
        agents_md_path.write_text("   \n \t  ")
        msg = build_system_message(tmpdir)
        assert msg == COGNITO_SYSTEM_PROMPT

def test_build_system_message_present():
    with tempfile.TemporaryDirectory() as tmpdir:
        agents_md_path = Path(tmpdir) / "AGENTS.md"
        agents_md_path.write_text("Custom instruction.")
        msg = build_system_message(tmpdir)
        expected = (
            f"{COGNITO_SYSTEM_PROMPT}\n\n---\n\n"
            f"Contexto específico de este repositorio (AGENTS.md):\n\nCustom instruction."
        )
        assert msg == expected

@pytest.mark.asyncio
async def test_agent_loop_system_message_integration(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. Configurar directorios y mocks
        tmp_path = Path(tmpdir)
        monkeypatch.setattr("app.core.session_manager.Path.home", lambda: tmp_path)

        # Crear un AGENTS.md ficticio en el cwd
        cwd = tmp_path / "my-repo"
        cwd.mkdir()
        agents_md_path = cwd / "AGENTS.md"
        agents_md_path.write_text("Only test here.")

        # Mock del agent_loop para capturar los mensajes finales
        captured_messages = []
        async def mock_agent_loop(messages, tools, context, backend_router, model_params=None):
            nonlocal captured_messages
            captured_messages = messages
            from app.core.events import TextDeltaEvent, DoneEvent
            yield TextDeltaEvent(content="Hello world")
            yield DoneEvent(stop_reason="end_turn")

        monkeypatch.setattr("app.api.routes.ai_agents.agent_loop", mock_agent_loop)

        # 2. Primera petición (sesión nueva)
        request = AgentLoopRequest(
            messages=[{"role": "user", "content": "How are you?"}],
            cwd=str(cwd)
        )
        response = await run_agent_loop(request)

        # Consumir stream para asegurar la ejecución del generador
        events = []
        async for line in response.body_iterator:
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))

        session_id = events[0]["session_id"]

        # Verificar primer mensaje que llega al loop
        assert len(captured_messages) == 2
        assert captured_messages[0]["role"] == "system"
        assert "Only test here." in captured_messages[0]["content"]
        assert captured_messages[1]["role"] == "user"
        assert captured_messages[1]["content"] == "How are you?"

        # Verificar persistencia en el .jsonl: NO debe estar el system message
        sm = SessionManager(sessions_dir=tmp_path / ".cognito" / "sessions")
        persisted_messages = sm.get_effective_messages(session_id)
        assert len(persisted_messages) == 2  # Solo "user" y "assistant" persistidos por el loop de streaming
        assert all(m["role"] != "system" for m in persisted_messages)

        # 3. Segunda petición (sesión existente)
        request_continue = AgentLoopRequest(
            messages=[{"role": "user", "content": "Tell me more"}],
            cwd=str(cwd),
            session_id=session_id
        )
        captured_messages = []
        response_continue = await run_agent_loop(request_continue)
        async for _ in response_continue.body_iterator:
            pass

        # El primer mensaje debe seguir siendo el system_prompt calculado en caliente
        assert len(captured_messages) == 4 # system_prompt + user(how are you) + assistant(hello world) + user(tell me more)
        assert captured_messages[0]["role"] == "system"
        assert "Only test here." in captured_messages[0]["content"]
        assert captured_messages[1]["role"] == "user"
        assert captured_messages[2]["role"] == "assistant"
        assert captured_messages[3]["role"] == "user"

@pytest.mark.asyncio
async def test_agent_loop_consecutive_system_messages_under_compaction(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        monkeypatch.setattr("app.core.session_manager.Path.home", lambda: tmp_path)

        cwd = tmp_path / "my-repo"
        cwd.mkdir()
        agents_md_path = cwd / "AGENTS.md"
        agents_md_path.write_text("Repo instructions.")

        sm = SessionManager(sessions_dir=tmp_path / ".cognito" / "sessions")
        session_id = sm.create(str(cwd))

        # Añadir muchos mensajes para que pase el umbral bajo de compactado
        for i in range(15):
            sm.append_message(session_id, "user", "a" * 100)
            sm.append_message(session_id, "assistant", "b" * 100)

        # Mock compactador y router
        mock_router = MagicMock()
        mock_router.generate = AsyncMock(return_value={"response": "Preserved summary content"})
        monkeypatch.setattr("app.api.routes.ai_agents.backend_router", mock_router)

        captured_messages = []
        async def mock_agent_loop(messages, tools, context, backend_router, model_params=None):
            nonlocal captured_messages
            captured_messages = messages
            from app.core.events import TextDeltaEvent, DoneEvent
            yield TextDeltaEvent(content="Done")
            yield DoneEvent(stop_reason="end_turn")

        monkeypatch.setattr("app.api.routes.ai_agents.agent_loop", mock_agent_loop)

        # Forzar que should_compact retorne True directamente
        monkeypatch.setattr("app.api.routes.ai_agents.should_compact", AsyncMock(return_value=True))

        request = AgentLoopRequest(
            messages=[{"role": "user", "content": "post compaction request"}],
            cwd=str(cwd),
            session_id=session_id
        )

        response = await run_agent_loop(request)
        async for _ in response.body_iterator:
            pass

        # Verificar que el loop reciba consecutive system messages:
        # index 0: Persona/AGENTS.md (System message generado en caliente)
        # index 1: Compacted history summary (System message persistido en el historial)
        assert len(captured_messages) >= 3
        assert captured_messages[0]["role"] == "system"
        assert "Repo instructions." in captured_messages[0]["content"]
        assert captured_messages[1]["role"] == "system"
        assert "Preserved summary content" in captured_messages[1]["content"]
