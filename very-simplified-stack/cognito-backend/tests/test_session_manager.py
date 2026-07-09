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
