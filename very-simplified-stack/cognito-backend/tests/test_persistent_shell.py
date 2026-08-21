import json
import os
import tempfile
import pytest
from pathlib import Path

from app.core.tools.base import ToolContext
from app.core.tools.persistent_shell_tool import (
    PersistentShellTool,
    PersistentShellSessionManager,
)


@pytest.fixture
def temp_workspace():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def tool_context(temp_workspace):
    return ToolContext(
        cwd=temp_workspace,
        trusted=True,
        protected_files=set(),
    )


@pytest.fixture
def shell_tool():
    manager = PersistentShellSessionManager()
    return PersistentShellTool(manager=manager)


@pytest.mark.asyncio
async def test_persistent_shell_basic_and_state_persistence(tool_context, shell_tool, temp_workspace):
    session_id = "test_session_1"

    # 1. Check initial echo
    res1 = await shell_tool.execute(
        {"command": "echo 'hello persistent'", "session_id": session_id},
        tool_context,
    )
    assert not res1.is_error
    assert "hello persistent" in res1.output

    # 2. Change working directory
    target_dir = os.path.realpath(temp_workspace)
    subdir = Path(target_dir) / "subdir"
    subdir.mkdir()

    res2 = await shell_tool.execute(
        {"command": f"cd {subdir.name}", "session_id": session_id},
        tool_context,
    )
    assert not res2.is_error

    res3 = await shell_tool.execute(
        {"command": "pwd", "session_id": session_id},
        tool_context,
    )
    assert not res3.is_error
    assert res3.output.strip() == str(subdir)

    # 3. Export environment variable
    res4 = await shell_tool.execute(
        {"command": "export MY_PERSISTENT_VAR=cognito_123", "session_id": session_id},
        tool_context,
    )
    assert not res4.is_error

    res5 = await shell_tool.execute(
        {"command": "echo $MY_PERSISTENT_VAR", "session_id": session_id},
        tool_context,
    )
    assert not res5.is_error
    assert res5.output.strip() == "cognito_123"

    # Cleanup
    await shell_tool.execute({"command": "__kill__", "session_id": session_id}, tool_context)


@pytest.mark.asyncio
async def test_persistent_shell_internal_commands(tool_context, shell_tool, temp_workspace):
    session_id = "test_session_internal"

    # Initialize session
    await shell_tool.execute(
        {"command": "sleep 100 &", "session_id": session_id},
        tool_context,
    )

    # __get_state__
    res_state = await shell_tool.execute(
        {"command": "__get_state__", "session_id": session_id},
        tool_context,
    )
    assert not res_state.is_error
    state_data = json.loads(res_state.output)

    assert state_data["session_id"] == session_id
    assert state_data["is_active"] is True
    assert state_data["shell_pid"] is not None
    assert isinstance(state_data["child_pids"], list)
    assert len(state_data["child_pids"]) >= 1

    child_pid = state_data["child_pids"][0]

    # __kill__
    res_kill = await shell_tool.execute(
        {"command": "__kill__", "session_id": session_id},
        tool_context,
    )
    assert not res_kill.is_error
    assert "terminated" in res_kill.output.lower()

    # Check state after kill
    res_state_post = await shell_tool.execute(
        {"command": "__get_state__", "session_id": session_id},
        tool_context,
    )
    state_data_post = json.loads(res_state_post.output)
    assert state_data_post["is_active"] is False

    # Verify background process was killed
    try:
        os.kill(child_pid, 0)
        process_alive = True
    except OSError:
        process_alive = False
    assert not process_alive, f"Child process {child_pid} was not killed!"


@pytest.mark.asyncio
async def test_persistent_shell_timeout_and_recovery(tool_context, shell_tool):
    session_id = "test_session_timeout"

    # Command times out
    res = await shell_tool.execute(
        {"command": "sleep 5", "timeout_seconds": 1, "session_id": session_id},
        tool_context,
    )
    assert res.is_error
    assert "timed out" in res.output

    # Shell recovers and processes next command
    res_next = await shell_tool.execute(
        {"command": "echo 'recovered'", "session_id": session_id},
        tool_context,
    )
    assert not res_next.is_error
    assert "recovered" in res_next.output

    # Cleanup
    await shell_tool.execute({"command": "__kill__", "session_id": session_id}, tool_context)


@pytest.mark.asyncio
async def test_persistent_shell_sudo_rejection(tool_context, shell_tool):
    res = await shell_tool.execute(
        {"command": "sudo ls", "session_id": "test_sudo"},
        tool_context,
    )
    assert res.is_error
    assert "strictly forbidden" in res.output


@pytest.mark.asyncio
async def test_persistent_shell_command_error(tool_context, shell_tool):
    session_id = "test_cmd_err"
    res = await shell_tool.execute(
        {"command": "ls /non_existent_file_directory_12345", "session_id": session_id},
        tool_context,
    )
    assert res.is_error
    assert "No such file or directory" in res.output

    # Cleanup
    await shell_tool.execute({"command": "__kill__", "session_id": session_id}, tool_context)
