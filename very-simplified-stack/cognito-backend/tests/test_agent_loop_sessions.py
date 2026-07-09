import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from app.api.routes.ai_agents import AgentLoopRequest, run_agent_loop
from app.core.session_manager import SessionManager
from app.core.events import SessionInfoEvent, DoneEvent, TextDeltaEvent

@pytest.fixture
def session_manager_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

@pytest.mark.asyncio
async def test_agent_loop_session_integration(session_manager_dir, monkeypatch):
    # Mock SessionManager's sessions_dir
    monkeypatch.setattr("app.core.session_manager.Path.home", lambda: session_manager_dir)

    # Mock backend_router.generate_with_tools (used in agent_loop)
    mock_router = MagicMock()
    async def mock_gen(*args, **kwargs):
        yield {"token": "Hello from assistant"}
    mock_router.generate_with_tools = mock_gen
    monkeypatch.setattr("app.api.routes.ai_agents.backend_router", mock_router)

    cwd = str(Path("/tmp/fake-repo").resolve())
    request = AgentLoopRequest(
        messages=[{"role": "user", "content": "How are you?"}],
        cwd=cwd
    )

    response = await run_agent_loop(request)

    # SSE stream parsing
    events = []
    async for line in response.body_iterator:
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))

    # Verify events
    assert events[0]["type"] == "session_info"
    session_id = events[0]["session_id"]
    assert events[0]["is_new"] is True

    assert any(e["type"] == "text_delta" and "Hello" in e["content"] for e in events)
    assert any(e["type"] == "done" for e in events)

    # Verify persistence
    sm = SessionManager(sessions_dir=session_manager_dir / ".cognito" / "sessions")
    msgs = sm.get_effective_messages(session_id)
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == "How are you?"
    assert msgs[1]["role"] == "assistant"
    assert "Hello" in msgs[1]["content"]

@pytest.mark.asyncio
async def test_agent_loop_compaction_integration(session_manager_dir, monkeypatch):
    monkeypatch.setattr("app.core.session_manager.Path.home", lambda: session_manager_dir)

    sm = SessionManager(sessions_dir=session_manager_dir / ".cognito" / "sessions")
    cwd = str(Path("/tmp/fake-repo").resolve())
    session_id = sm.create(cwd)

    # Add many messages to trigger compaction
    for i in range(20):
        sm.append_message(session_id, "user", "a" * 1000)
        sm.append_message(session_id, "assistant", "b" * 1000)

    # Mock compaction
    mock_router = MagicMock()
    mock_router.generate = AsyncMock(return_value={"response": "Preserved summary"})
    async def mock_gen(*args, **kwargs):
        yield {"token": "Response after compaction"}
    mock_router.generate_with_tools = mock_gen
    monkeypatch.setattr("app.api.routes.ai_agents.backend_router", mock_router)

    # Set low threshold
    monkeypatch.setenv("COGNITO_SESSION_COMPACTION_THRESHOLD_TOKENS", "10")

    request = AgentLoopRequest(
        messages=[{"role": "user", "content": "next msg"}],
        cwd=cwd,
        session_id=session_id
    )

    response = await run_agent_loop(request)

    # Consume response to trigger persistence
    async for _ in response.body_iterator:
        pass

    # Verify session file has compaction record
    msgs = sm.get_effective_messages(session_id)
    assert msgs[0]["role"] == "system"
    assert "Preserved summary" in msgs[0]["content"]

    # And the last messages + the new one
    assert any(m["content"] == "next msg" for m in msgs)
