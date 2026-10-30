import os
import pytest
from pathlib import Path
from unittest.mock import patch

from app.core.tools.read_tool import ReadTool
from app.core.tools.edit_tool import EditTool
from app.core.tools.write_tool import WriteTool
from app.core.tools.base import ToolContext

try:
    from app.core.path_safety import resolve_in_workspace
except ImportError:
    resolve_in_workspace = None


@pytest.fixture
def mock_context(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Create dummy files
    (workspace / "sample.txt").write_text("hello world\n", encoding="utf-8")
    (workspace / ".env").write_text("SECRET_KEY=12345\n", encoding="utf-8")

    # Outside secret
    outside = tmp_path / "outside_secret.txt"
    outside.write_text("CONFIDENTIAL\n", encoding="utf-8")

    # Symlink pointing outside
    symlink_outside = workspace / "link_outside.txt"
    try:
        os.symlink(outside, symlink_outside)
    except Exception:
        pass

    # Symlink pointing to protected file inside workspace
    symlink_protected = workspace / "alias_env.txt"
    try:
        os.symlink(workspace / ".env", symlink_protected)
    except Exception:
        pass

    context = ToolContext(
        cwd=str(workspace),
        session_id="test_session",
        trusted=True,
        protected_files={".env", "config/secrets.json"},
    )
    return context, workspace, outside


@pytest.mark.asyncio
async def test_read_tool_path_traversal_blocked(mock_context):
    context, workspace, outside = mock_context
    read_tool = ReadTool()

    # Relative ../ traversal
    res1 = await read_tool.execute({"path": "../outside_secret.txt"}, context)
    assert res1.is_error is True

    # Absolute path
    res2 = await read_tool.execute({"path": str(outside)}, context)
    assert res2.is_error is True

    # Symlink pointing outside
    res3 = await read_tool.execute({"path": "link_outside.txt"}, context)
    assert res3.is_error is True


@pytest.mark.asyncio
async def test_edit_tool_path_traversal_blocked(mock_context):
    context, workspace, outside = mock_context
    edit_tool = EditTool()

    original_outside_content = outside.read_text(encoding="utf-8")

    # Relative ../ traversal
    res1 = await edit_tool.execute({"path": "../outside_secret.txt", "old_str": "CONFIDENTIAL", "new_str": "HACKED"}, context)
    assert res1.is_error is True
    assert outside.read_text(encoding="utf-8") == original_outside_content

    # Absolute path
    res2 = await edit_tool.execute({"path": str(outside), "old_str": "CONFIDENTIAL", "new_str": "HACKED"}, context)
    assert res2.is_error is True
    assert outside.read_text(encoding="utf-8") == original_outside_content

    # Symlink pointing outside
    res3 = await edit_tool.execute({"path": "link_outside.txt", "old_str": "CONFIDENTIAL", "new_str": "HACKED"}, context)
    assert res3.is_error is True
    assert outside.read_text(encoding="utf-8") == original_outside_content


@pytest.mark.asyncio
async def test_edit_tool_atomic_write_failure_leaves_file_intact(mock_context):
    context, workspace, _ = mock_context
    edit_tool = EditTool()

    file_to_edit = workspace / "sample.txt"
    original_content = file_to_edit.read_text(encoding="utf-8")

    # Mock os.replace to fail midway
    with patch("os.replace", side_effect=OSError("Simulated disk error")):
        res = await edit_tool.execute({"path": "sample.txt", "old_str": "hello", "new_str": "goodbye"}, context)
        assert res.is_error is True
        assert file_to_edit.read_text(encoding="utf-8") == original_content


@pytest.mark.asyncio
async def test_write_tool_symlink_to_protected_file_blocked(mock_context):
    context, workspace, _ = mock_context
    write_tool = WriteTool()

    protected_file = workspace / ".env"
    original_env = protected_file.read_text(encoding="utf-8")

    # Attempt to write via symlink alias_env.txt -> .env
    res = await write_tool.execute({"path": "alias_env.txt", "content": "SECRET_KEY=HACKED\n"}, context)
    assert res.is_error is True
    assert "protected" in res.output.lower() or "protegido" in res.output.lower() or "denied" in res.output.lower()
    assert protected_file.read_text(encoding="utf-8") == original_env


@pytest.mark.asyncio
async def test_write_tool_path_traversal_blocked(mock_context):
    context, workspace, outside = mock_context
    write_tool = WriteTool()

    original_outside = outside.read_text(encoding="utf-8")

    res = await write_tool.execute({"path": "../outside_secret.txt", "content": "OVERWRITTEN\n"}, context)
    assert res.is_error is True
    assert outside.read_text(encoding="utf-8") == original_outside


def test_resolve_in_workspace_helper(tmp_path):
    if resolve_in_workspace is None:
        pytest.skip("resolve_in_workspace helper not implemented yet.")

    workspace = tmp_path / "ws"
    workspace.mkdir()

    inside = workspace / "valid.txt"
    inside.write_text("ok", encoding="utf-8")

    outside = tmp_path / "outside.txt"
    outside.write_text("no", encoding="utf-8")

    symlink_outside = workspace / "sym_out.txt"
    os.symlink(outside, symlink_outside)

    # Valid
    assert resolve_in_workspace("valid.txt", str(workspace)) == inside.resolve()

    # Traversal relative
    assert resolve_in_workspace("../outside.txt", str(workspace)) is None

    # Absolute
    assert resolve_in_workspace(str(outside), str(workspace)) is None

    # Symlink outside
    assert resolve_in_workspace("sym_out.txt", str(workspace)) is None
