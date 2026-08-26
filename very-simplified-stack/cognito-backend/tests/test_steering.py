import asyncio
import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.core.steering import SteeringManager, steering_manager
from app.core.session_manager import SessionManager
from app.core.agent_loop import agent_loop
from app.core.tools.base import AgentTool, ToolContext, ToolResult
from app.core.events import TextDeltaEvent, ToolCallEvent, ToolResultEvent, DoneEvent
from app.core.session.message_deriver import derive_messages_for_llm, DerivationConfig


class DummyTool(AgentTool):
    @property
    def name(self) -> str:
        return "dummy_tool"

    @property
    def description(self) -> str:
        return "Dummy tool for testing"

    @property
    def parameters_schema(self) -> dict:
        return {"type": "object", "properties": {}}

    async def execute(self, arguments: dict, context: ToolContext) -> ToolResult:
        return ToolResult(is_error=False, output="dummy_result")


@pytest.mark.asyncio
async def test_steering_manager_basic():
    sm = SteeringManager()
    q1 = sm.get_queue("sess-1")
    l1 = sm.get_lock("sess-1")

    assert sm.get_queue("sess-1") is q1
    assert sm.get_lock("sess-1") is l1

    await sm.post_steering_message("sess-1", "use pytest instead")
    assert not q1.empty()
    msg = q1.get_nowait()
    assert msg == "use pytest instead"

    sm.clear_session("sess-1")
    q2 = sm.get_queue("sess-1")
    assert q2 is not q1


def test_steering_endpoint(tmp_path, monkeypatch):
    sm = SessionManager(sessions_dir=tmp_path)
    session_id = sm.create(cwd="/tmp/workspace")

    client = TestClient(app)

    # Patch SessionManager in ai_agents to use temp dir
    monkeypatch.setattr("app.api.routes.ai_agents.SessionManager", lambda: sm)

    # Test valid steer request
    response = client.post(
        f"/api/agent/sessions/{session_id}/steer",
        json={"message": "No, use library X instead"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["session_id"] == session_id
    assert data["message"] == "No, use library X instead"

    # Check message was queued in steering_manager
    queue = steering_manager.get_queue(session_id)
    assert not queue.empty()
    assert queue.get_nowait() == "No, use library X instead"

    # Test invalid empty message
    response_empty = client.post(
        f"/api/agent/sessions/{session_id}/steer",
        json={"message": "   "}
    )
    assert response_empty.status_code == 400

    # Test non-existent session
    response_404 = client.post(
        "/api/agent/sessions/non-existent-session/steer",
        json={"message": "hello"}
    )
    assert response_404.status_code == 404


@pytest.mark.asyncio
async def test_agent_loop_steering_injection_before_llm(tmp_path):
    sm = SessionManager(sessions_dir=tmp_path)
    session_id = sm.create(cwd="/tmp")

    steering_queue = asyncio.Queue()
    await steering_queue.put("No, use asyncio instead")

    history_lock = asyncio.Lock()

    # Mock backend router
    backend_router = MagicMock()
    async def mock_generate(messages, tools_schema, model_params=None):
        # Verify steering message was injected into messages before LLM generation
        assert any(
            m.get("role") == "user" and "[STEERING INPUT] No, use asyncio instead" in m.get("content", "")
            for m in messages
        )
        yield {"token": "Understood"}

    backend_router.generate_with_tools = mock_generate

    initial_messages = [{"role": "user", "content": "Write a program"}]
    tool_context = ToolContext(cwd="/tmp", trusted=True, protected_files=[])

    events = []
    async for event in agent_loop(
        messages=initial_messages,
        tools=[],
        context=tool_context,
        backend_router=backend_router,
        steering_queue=steering_queue,
        history_lock=history_lock,
        session_manager=sm,
        session_id=session_id
    ):
        events.append(event)

    assert any(isinstance(e, TextDeltaEvent) and e.content == "Understood" for e in events)
    assert any(isinstance(e, DoneEvent) for e in events)

    # Check session history persisted the steering message
    persisted_messages = sm.get_effective_messages(session_id)
    assert any("[STEERING INPUT] No, use asyncio instead" in m.get("content", "") for m in persisted_messages)


@pytest.mark.asyncio
async def test_agent_loop_steering_injection_before_tool_exec(tmp_path):
    sm = SessionManager(sessions_dir=tmp_path)
    session_id = sm.create(cwd="/tmp")

    steering_queue = asyncio.Queue()
    history_lock = asyncio.Lock()

    dummy_tool = DummyTool()

    backend_router = MagicMock()

    turn_count = 0
    async def mock_generate(messages, tools_schema, model_params=None):
        nonlocal turn_count
        turn_count += 1
        if turn_count == 1:
            # First turn: yield a tool call, and put steering input into queue while LLM was processing
            await steering_queue.put("Wait, do not call dummy_tool with bad args")
            yield {
                "tool_calls": [{
                    "id": "call_1",
                    "function": {"name": "dummy_tool", "arguments": {}}
                }]
            }
        else:
            yield {"token": "Done with steering"}

    backend_router.generate_with_tools = mock_generate

    initial_messages = [{"role": "user", "content": "Run tool"}]
    tool_context = ToolContext(cwd="/tmp", trusted=True, protected_files=[])

    events = []
    async for event in agent_loop(
        messages=initial_messages,
        tools=[dummy_tool],
        context=tool_context,
        backend_router=backend_router,
        steering_queue=steering_queue,
        history_lock=history_lock,
        session_manager=sm,
        session_id=session_id
    ):
        events.append(event)

    # Verify steering message was queued and drained
    assert steering_queue.empty()

    # Verify session persisted steering message
    persisted_messages = sm.get_effective_messages(session_id)
    assert any("[STEERING INPUT] Wait, do not call dummy_tool with bad args" in m.get("content", "") for m in persisted_messages)


@pytest.mark.asyncio
async def test_steering_persistence_and_resumption_after_process_restart(tmp_path):
    # 1. Initialize session manager and create session
    sm = SessionManager(sessions_dir=tmp_path)
    session_id = sm.create(cwd=str(tmp_path))

    sm_steering = SteeringManager()

    # 2. Post steering message before agent loop consumes it
    steering_id = await sm_steering.post_steering_message(
        session_id, "Use strict typing and pytest", session_manager=sm
    )

    # Verify steering message was persisted to .jsonl with delivered: False
    undelivered = sm.get_undelivered_steering_messages(session_id)
    assert len(undelivered) == 1
    assert undelivered[0]["id"] == steering_id
    assert undelivered[0]["content"] == "Use strict typing and pytest"

    # 3. Simulate backend process restart / worker crash (new SteeringManager instance, memory cleared)
    sm_restarted = SteeringManager()
    sm_session_restarted = SessionManager(sessions_dir=tmp_path)

    backend_router = MagicMock()
    received_messages = []

    async def mock_generate(messages, tools_schema, model_params=None):
        received_messages.append(list(messages))
        yield {"token": "Refactored with pytest"}

    backend_router.generate_with_tools = mock_generate

    initial_messages = [{"role": "user", "content": "Refactor code"}]
    tool_context = ToolContext(cwd=str(tmp_path), trusted=True, protected_files=[])
    history_lock = sm_restarted.get_lock(session_id)
    steering_queue = sm_restarted.get_queue(session_id)

    # 4. Resume session in restarted backend process
    events = []
    async for event in agent_loop(
        messages=initial_messages,
        tools=[],
        context=tool_context,
        backend_router=backend_router,
        steering_queue=steering_queue,
        history_lock=history_lock,
        session_manager=sm_session_restarted,
        session_id=session_id,
        steering_manager=sm_restarted
    ):
        events.append(event)

    # 5. Assertions for first turn after resumption
    assert len(received_messages) == 1
    messages_in_turn = received_messages[0]
    assert any(
        m.get("role") == "user" and "[STEERING INPUT] Use strict typing and pytest" in m.get("content", "")
        for m in messages_in_turn
    )

    # Verify persistent state: undelivered is now empty, and delivered is True in .jsonl
    undelivered_after = sm_session_restarted.get_undelivered_steering_messages(session_id)
    assert len(undelivered_after) == 0

    # 6. Run a second turn deriving messages from session history to ensure no duplicate steering injection occurs
    received_messages.clear()
    turn2_messages = await derive_messages_for_llm(
        session_id, DerivationConfig(cwd=str(tmp_path), sessions_dir=tmp_path)
    )

    async for event in agent_loop(
        messages=turn2_messages,
        tools=[],
        context=tool_context,
        backend_router=backend_router,
        steering_queue=steering_queue,
        history_lock=history_lock,
        session_manager=sm_session_restarted,
        session_id=session_id,
        steering_manager=sm_restarted
    ):
        pass

    assert len(received_messages) == 1
    messages_in_second_turn = received_messages[0]
    steering_occurrences = sum(
        1 for m in messages_in_second_turn
        if m.get("role") == "user" and "[STEERING INPUT] Use strict typing and pytest" in m.get("content", "")
    )
    assert steering_occurrences == 1
