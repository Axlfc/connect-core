import json
import pytest
import tempfile
from pathlib import Path

from app.api.routes.ai_agents import AgentLoopRequest, run_agent_loop
from app.core.session_manager import SessionManager
from app.core.events import TextDeltaEvent, ToolCallEvent, ToolResultEvent, DoneEvent


@pytest.mark.asyncio
async def test_aud026_checkpointing_and_resumption(monkeypatch):
    """
    Acceptance test for AUD-026:
    Simulates a crash/interruption mid-way through a multi-turn task.
    Confirms that upon restarting / resuming with session_id, execution resumes from the last completed turn
    rather than starting from zero.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        monkeypatch.setattr("app.core.session_manager.Path.home", lambda: tmp_path)

        cwd = tmp_path / "workspace"
        cwd.mkdir()

        # Phase 1: Run Turn 1 (Call a tool), then simulate process crash right after Turn 1 completed.
        turn_counter = 0

        async def mock_agent_loop_phase1(messages, tools, context, backend_router, model_params=None, **kwargs):
            nonlocal turn_counter
            turn_counter += 1
            if turn_counter == 1:
                # Turn 1: Assistant requests tool call
                yield TextDeltaEvent(content="I will run tool turn 1.")
                yield ToolCallEvent(tool_call_id="call_t1", tool_name="read", arguments={"path": "test.txt"})
                yield ToolResultEvent(tool_call_id="call_t1", tool_name="read", output="file content turn 1", is_error=False)
                # Crash / Interruption occurs right after turn 1 completed before completing the entire task
                raise RuntimeError("Process crashed mid-task during turn 1!")

        monkeypatch.setattr("app.api.routes.ai_agents.agent_loop", mock_agent_loop_phase1)

        req1 = AgentLoopRequest(
            messages=[{"role": "user", "content": "Execute multi-turn task"}],
            cwd=str(cwd)
        )

        resp1 = await run_agent_loop(req1)

        session_id = None
        # Consume stream until crash
        try:
            async for line in resp1.body_iterator:
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    if data.get("type") == "session_info":
                        session_id = data.get("session_id")
        except RuntimeError:
            pass

        assert session_id is not None, "Session ID should have been created before crash"

        # Verify that Turn 1 was checkpointed atomically despite process crash
        sm = SessionManager(sessions_dir=tmp_path / ".cognito" / "sessions")
        effective_msgs = sm.get_effective_messages(session_id)

        # Checkpointed messages should include:
        # 1. user prompt
        # 2. assistant message calling tool
        # 3. tool result for call_t1
        assert len(effective_msgs) == 3
        assert effective_msgs[0]["role"] == "user"
        assert effective_msgs[1]["role"] == "assistant"
        assert effective_msgs[2]["role"] == "tool"
        assert effective_msgs[2]["name"] == "read"
        assert "file content turn 1" in effective_msgs[2]["content"]

        # Phase 2: Restart backend process (simulated by new mock and resuming session_id)
        captured_messages_phase2 = []

        async def mock_agent_loop_phase2(messages, tools, context, backend_router, model_params=None, **kwargs):
            nonlocal captured_messages_phase2
            captured_messages_phase2 = messages
            # Turn 2: Completes task from resumed state
            yield TextDeltaEvent(content="Task completed from turn 2 checkpoint.")
            yield DoneEvent(stop_reason="end_turn")

        monkeypatch.setattr("app.api.routes.ai_agents.agent_loop", mock_agent_loop_phase2)

        # Resume with same session_id and original/continued prompt
        req2 = AgentLoopRequest(
            messages=[{"role": "user", "content": "Execute multi-turn task"}],
            cwd=str(cwd),
            session_id=session_id
        )

        resp2 = await run_agent_loop(req2)
        async for _ in resp2.body_iterator:
            pass

        # Confirm that agent loop in phase 2 received the exact checkpointed history (Turn 1 completed state)
        # and did NOT duplicate the user message or restart from scratch
        assert len(captured_messages_phase2) >= 4
        # Index 0: System prompt (generated dynamically for cwd)
        assert captured_messages_phase2[0]["role"] == "system"
        # Index 1: User prompt
        assert captured_messages_phase2[1]["role"] == "user"
        assert captured_messages_phase2[1]["content"] == "Execute multi-turn task"
        # Index 2: Assistant tool call from Turn 1
        assert captured_messages_phase2[2]["role"] == "assistant"
        # Index 3: Tool result from Turn 1
        assert captured_messages_phase2[3]["role"] == "tool"
        assert "file content turn 1" in captured_messages_phase2[3]["content"]

        # Confirm final persisted session has full history including phase 2 completion
        final_messages = sm.get_effective_messages(session_id)
        assert len(final_messages) == 4
        assert final_messages[-1]["role"] == "assistant"
        assert final_messages[-1]["content"] == "Task completed from turn 2 checkpoint."
