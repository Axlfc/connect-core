import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from app.api.routes.ai_agents import AgentLoopRequest, run_agent_loop, fork_session
from app.core.session_manager import SessionManager
from app.core.compaction import compact
from app.core.events import TextDeltaEvent, ToolCallEvent, ToolResultEvent, DoneEvent


@pytest.mark.asyncio
async def test_session_branching_divergence_no_cross_contamination(monkeypatch):
    """
    Acceptance test for AUD-015:
    Branching a session at turn N produces a new session with identical history up to N
    and independent history after N, with zero cross-contamination.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        monkeypatch.setattr("app.core.session_manager.Path.home", lambda: tmp_path)

        sm = SessionManager(sessions_dir=tmp_path / ".cognito" / "sessions")
        parent_id = sm.create(str(tmp_path))

        # Turn 1
        sm.append_message(parent_id, "user", "Turn 1 request")
        sm.append_message(parent_id, "assistant", "Turn 1 response")

        # Turn 2
        sm.append_message(parent_id, "user", "Turn 2 request")
        sm.append_message(parent_id, "assistant", "Turn 2 response")

        # Turn 3
        sm.append_message(parent_id, "user", "Turn 3 request")
        sm.append_message(parent_id, "assistant", "Turn 3 response")

        # Fork at Turn 2
        child_id = sm.fork_from(parent_id, turn=2)

        # Verify initial state of child session
        child_meta = sm.open(child_id)
        assert child_meta.parent_session_id == parent_id
        assert child_meta.branch_turn == 2

        parent_msgs = sm.get_effective_messages(parent_id)
        child_msgs = sm.get_effective_messages(child_id)

        assert len(parent_msgs) == 6
        assert len(child_msgs) == 4
        assert child_msgs[0]["content"] == "Turn 1 request"
        assert child_msgs[1]["content"] == "Turn 1 response"
        assert child_msgs[2]["content"] == "Turn 2 request"
        assert child_msgs[3]["content"] == "Turn 2 response"

        # Make both branches diverge with new independent messages
        sm.append_message(parent_id, "user", "Parent Turn 4 request")
        sm.append_message(parent_id, "assistant", "Parent Turn 4 response")

        sm.append_message(child_id, "user", "Child Turn 3 alternative request")
        sm.append_message(child_id, "assistant", "Child Turn 3 alternative response")

        # Confirm zero cross-contamination
        final_parent_msgs = sm.get_effective_messages(parent_id)
        final_child_msgs = sm.get_effective_messages(child_id)

        assert len(final_parent_msgs) == 8
        assert len(final_child_msgs) == 6

        parent_contents = [m["content"] for m in final_parent_msgs]
        child_contents = [m["content"] for m in final_child_msgs]

        assert "Parent Turn 4 request" in parent_contents
        assert "Parent Turn 4 request" not in child_contents

        assert "Child Turn 3 alternative request" in child_contents
        assert "Child Turn 3 alternative request" not in parent_contents


@pytest.mark.asyncio
async def test_branching_with_compaction_and_context_ledger(monkeypatch):
    """
    Verifies that context compaction and context ledger (AUD-013) function correctly
    on branched sessions.
    """
    backend_router = MagicMock()
    backend_router.generate = AsyncMock(return_value={"response": "Summary of branched session"})

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        sm = SessionManager(sessions_dir=tmp_path / ".cognito" / "sessions")
        parent_id = sm.create(str(tmp_path))

        # Turn 1 with tool call
        sm.append_message(parent_id, "user", "Inspect file main.py")
        sm.append_message(
            parent_id,
            "assistant",
            "Reading main.py",
            tool_calls=[{"id": "tc1", "type": "function", "function": {"name": "read_file", "arguments": '{"path": "main.py"}'}}]
        )
        sm.append_message(parent_id, "tool", "def main(): pass", tool_name="read_file", tool_call_id="tc1")

        # Turn 2
        sm.append_message(parent_id, "user", "Inspect file utils.py")
        sm.append_message(
            parent_id,
            "assistant",
            "Reading utils.py",
            tool_calls=[{"id": "tc2", "type": "function", "function": {"name": "read_file", "arguments": '{"path": "utils.py"}'}}]
        )
        sm.append_message(parent_id, "tool", "def util(): pass", tool_name="read_file", tool_call_id="tc2")

        # Branch at Turn 1
        child_id = sm.fork_from(parent_id, turn=1)

        # Append messages to child
        sm.append_message(child_id, "user", "Branch turn 2: inspect config.py")
        sm.append_message(
            child_id,
            "assistant",
            "Reading config.py",
            tool_calls=[{"id": "tc3", "type": "function", "function": {"name": "read_file", "arguments": '{"path": "config.py"}'}}]
        )
        sm.append_message(child_id, "tool", "CONFIG = {}", tool_name="read_file", tool_call_id="tc3")

        # Compact child session with keep_last_n=0 so all messages go into ledger
        child_effective = sm.get_effective_messages(child_id)
        last_line = sm.get_last_line_index(child_id)
        summary, ledger = await compact(child_effective, keep_last_n=0, backend_router=backend_router)

        sm.append_compaction(child_id, summary, last_line, ledger)

        # Verify compacted messages in child session
        compacted_child_msgs = sm.get_effective_messages(child_id)
        assert len(compacted_child_msgs) > 0
        summary_msg = compacted_child_msgs[0]
        assert "Resumen de la conversación anterior" in summary_msg["content"]
        assert "main.py" in summary_msg["content"]
        assert "config.py" in summary_msg["content"]
        assert "utils.py" not in summary_msg["content"]  # utils.py was in Turn 2 of parent, not child


@pytest.mark.asyncio
async def test_branching_with_turn_checkpointing(monkeypatch):
    """
    Verifies that turn checkpointing (AUD-026) operates cleanly on branched sessions.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        monkeypatch.setattr("app.core.session_manager.Path.home", lambda: tmp_path)
        cwd = tmp_path / "workspace"
        cwd.mkdir()

        sm = SessionManager(sessions_dir=tmp_path / ".cognito" / "sessions")
        parent_id = sm.create(str(cwd))

        # Parent Turn 1
        sm.append_message(parent_id, "user", "Parent Turn 1")
        sm.append_message(parent_id, "assistant", "Parent Turn 1 Done")

        # Fork to child at Turn 1
        child_id = sm.fork_from(parent_id, turn=1)

        # Run agent loop on child session with mock loop that streams tool result and done
        async def mock_agent_loop(messages, tools, context, backend_router, model_params=None, **kwargs):
            yield TextDeltaEvent(content="Child turn assistant delta")
            yield ToolCallEvent(tool_call_id="call_child", tool_name="write", arguments={"path": "out.txt"})
            yield ToolResultEvent(tool_call_id="call_child", tool_name="write", output="wrote out.txt", is_error=False)
            yield DoneEvent(stop_reason="end_turn")

        monkeypatch.setattr("app.api.routes.ai_agents.agent_loop", mock_agent_loop)

        req = AgentLoopRequest(
            messages=[{"role": "user", "content": "Child Turn 2 User"}],
            cwd=str(cwd),
            session_id=child_id
        )

        resp = await run_agent_loop(req)
        async for _ in resp.body_iterator:
            pass

        # Checkpointed messages in child session:
        # 1. Parent Turn 1 User
        # 2. Parent Turn 1 Assistant
        # 3. Child Turn 2 User
        # 4. Child Turn 2 Assistant (tool call)
        # 5. Child Turn 2 Tool Result
        child_msgs = sm.get_effective_messages(child_id)
        assert len(child_msgs) == 5
        assert child_msgs[0]["content"] == "Parent Turn 1"
        assert child_msgs[1]["content"] == "Parent Turn 1 Done"
        assert child_msgs[2]["content"] == "Child Turn 2 User"
        assert child_msgs[3]["role"] == "assistant"
        assert child_msgs[4]["role"] == "tool"
        assert "wrote out.txt" in child_msgs[4]["content"]

        # Parent session should remain untouched
        parent_msgs = sm.get_effective_messages(parent_id)
        assert len(parent_msgs) == 2
        assert parent_msgs[0]["content"] == "Parent Turn 1"
        assert parent_msgs[1]["content"] == "Parent Turn 1 Done"
