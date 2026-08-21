import json
import pytest
import tempfile
from pathlib import Path
from app.core.session_manager import SessionManager

@pytest.fixture
def session_manager():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield SessionManager(sessions_dir=Path(tmpdir))

def test_session_lifecycle(session_manager):
    cwd = "/tmp/repo"
    session_id = session_manager.create(cwd)
    assert session_id is not None

    meta = session_manager.open(session_id)
    assert meta.cwd == str(Path(cwd).resolve())
    assert meta.message_count == 0

    session_manager.append_message(session_id, "user", "hello")
    session_manager.append_message(session_id, "assistant", "hi")

    meta = session_manager.open(session_id)
    assert meta.message_count == 2

    msgs = session_manager.get_effective_messages(session_id)
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[1]["content"] == "hi"

def test_continue_recent(session_manager):
    cwd = "/tmp/repo"
    s1 = session_manager.create(cwd)
    s2 = session_manager.create(cwd)

    # Update s1
    session_manager.append_message(s1, "user", "msg")

    recent = session_manager.continue_recent(cwd)
    assert recent == s1

def test_fork(session_manager):
    cwd = "/tmp/repo"
    s1 = session_manager.create(cwd)
    session_manager.append_message(s1, "user", "original")

    s2 = session_manager.fork_from(s1)
    assert s1 != s2

    msgs = session_manager.get_effective_messages(s2)
    assert len(msgs) == 1
    assert msgs[0]["content"] == "original"

def test_corrupt_line(session_manager):
    cwd = "/tmp/repo"
    session_id = session_manager.create(cwd)

    session_file = session_manager.sessions_dir / f"{session_id}.jsonl"
    with open(session_file, "a") as f:
        f.write("invalid json\n")
        f.write(json.dumps({"type": "message", "role": "user", "content": "valid", "ts": "..."}) + "\n")

    msgs = session_manager.get_effective_messages(session_id)
    assert len(msgs) == 1
    assert msgs[0]["content"] == "valid"

def test_rollback_turns(session_manager):
    cwd = "/tmp/repo"
    session_id = session_manager.create(cwd)

    # Turn 1
    session_manager.append_message(session_id, "user", "Hello turn 1")
    session_manager.append_message(session_id, "assistant", "Hi turn 1")

    # Turn 2
    session_manager.append_message(session_id, "user", "Question turn 2")
    session_manager.append_message(session_id, "assistant", "Answer turn 2", tool_calls=[{"name": "test"}])
    session_manager.append_message(session_id, "tool", "tool response", tool_name="test", tool_call_id="123")
    session_manager.append_message(session_id, "assistant", "Final turn 2")

    # Turn 3
    session_manager.append_message(session_id, "user", "Question turn 3")
    session_manager.append_message(session_id, "assistant", "Answer turn 3")

    meta = session_manager.open(session_id)
    assert meta.message_count == 8

    # Rollback 1 turn (should remove Turn 3)
    session_manager.rollback_turns(session_id, 1)

    meta = session_manager.open(session_id)
    assert meta.message_count == 6
    msgs = session_manager.get_effective_messages(session_id)
    assert len(msgs) == 6
    assert msgs[-1]["content"] == "Final turn 2"

    # Rollback 1 more turn (should remove Turn 2)
    session_manager.rollback_turns(session_id, 1)

    meta = session_manager.open(session_id)
    assert meta.message_count == 2
    msgs = session_manager.get_effective_messages(session_id)
    assert len(msgs) == 2
    assert msgs[0]["content"] == "Hello turn 1"
    assert msgs[1]["content"] == "Hi turn 1"

    # Rollback 5 turns (more turns than present - should remove Turn 1, leaving 0 messages)
    session_manager.rollback_turns(session_id, 5)

    meta = session_manager.open(session_id)
    assert meta.message_count == 0
    msgs = session_manager.get_effective_messages(session_id)
    assert len(msgs) == 0

def test_archive_session(session_manager):
    cwd = "/tmp/repo"
    session_id = session_manager.create(cwd)
    session_manager.append_message(session_id, "user", "test archive")

    archived_path = session_manager.archive_session(session_id)

    assert archived_path.exists()
    assert archived_path.parent == session_manager.sessions_dir / "archive"

    # Should no longer be in active index
    with pytest.raises(FileNotFoundError):
        session_manager.open(session_id)

    # Active file should no longer exist in sessions_dir
    active_file = session_manager.sessions_dir / f"{session_id}.jsonl"
    assert not active_file.exists()

def test_delete_session(session_manager):
    cwd = "/tmp/repo"
    session_id = session_manager.create(cwd)
    session_manager.append_message(session_id, "user", "test delete")

    session_manager.delete_session(session_id)

    # Should no longer be in active index
    with pytest.raises(FileNotFoundError):
        session_manager.open(session_id)

    # File should be deleted
    session_file = session_manager.sessions_dir / f"{session_id}.jsonl"
    assert not session_file.exists()

def test_nonexistent_session_errors(session_manager):
    bad_id = "non-existent-id"
    with pytest.raises(FileNotFoundError):
        session_manager.rollback_turns(bad_id, 1)

    with pytest.raises(FileNotFoundError):
        session_manager.archive_session(bad_id)

    with pytest.raises(FileNotFoundError):
        session_manager.delete_session(bad_id)
