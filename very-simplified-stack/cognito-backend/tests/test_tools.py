import pytest
import os
import tempfile
from pathlib import Path
from app.core.project_trust import ProjectTrustStore
from app.core.tools.base import ToolContext, ToolResult
from app.core.tools.read_tool import ReadTool
from app.core.tools.write_tool import WriteTool
from app.core.tools.edit_tool import EditTool
from app.core.tools.bash_tool import BashTool
from app.core.tools.unified_patch_tool import UnifiedPatchTool

@pytest.fixture
def temp_workspace():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir

@pytest.fixture
def tool_context(temp_workspace):
    return ToolContext(
        cwd=temp_workspace,
        trusted=True,
        protected_files={"protected.txt"}
    )

@pytest.mark.asyncio
async def test_read_tool(temp_workspace, tool_context):
    test_file = Path(temp_workspace) / "test.txt"
    test_file.write_text("hello world")

    tool = ReadTool()
    # Success
    result = await tool.execute({"path": "test.txt"}, tool_context)
    assert result.output == "hello world"
    assert not result.is_error

    # Path traversal / hidden
    result = await tool.execute({"path": "../test.txt"}, tool_context)
    assert result.is_error
    assert "Archivo o directorio no encontrado o no accesible" in result.output

@pytest.mark.asyncio
async def test_write_tool(temp_workspace, tool_context):
    tool = WriteTool()

    # Success
    result = await tool.execute({"path": "new.txt", "content": "data"}, tool_context)
    assert not result.is_error
    assert (Path(temp_workspace) / "new.txt").read_text() == "data"

    # Protected file
    result = await tool.execute({"path": "protected.txt", "content": "data"}, tool_context)
    assert result.is_error
    assert "Archivo protegido" in result.output

    # Untrusted
    tool_context.trusted = False
    result = await tool.execute({"path": "untrusted.txt", "content": "data"}, tool_context)
    assert result.is_error
    assert "no confiado" in result.output

@pytest.mark.asyncio
async def test_edit_tool(temp_workspace, tool_context):
    test_file = Path(temp_workspace) / "edit.txt"
    test_file.write_text("line 1\nline 2\nline 3")

    tool = EditTool()
    # Success
    result = await tool.execute({"path": "edit.txt", "old_str": "line 2", "new_str": "replaced"}, tool_context)
    assert not result.is_error
    assert "replaced" in test_file.read_text()

    # Not unique
    test_file.write_text("aaa\naaa")
    result = await tool.execute({"path": "edit.txt", "old_str": "aaa", "new_str": "bbb"}, tool_context)
    assert result.is_error
    assert "appears 2 times" in result.output

@pytest.mark.asyncio
async def test_bash_tool(temp_workspace, tool_context):
    tool = BashTool()

    # Success
    result = await tool.execute({"command": "echo 'hello'"}, tool_context)
    assert not result.is_error
    assert "hello" in result.output

    # sudo rejection
    result = await tool.execute({"command": "sudo ls"}, tool_context)
    assert result.is_error
    assert "strictly forbidden" in result.output

    # Timeout (mocking or using sleep)
    result = await tool.execute({"command": "sleep 2", "timeout_seconds": 1}, tool_context)
    assert result.is_error
    assert "timed out" in result.output

@pytest.mark.asyncio
async def test_unified_patch_tool_success(temp_workspace, tool_context):
    test_file = Path(temp_workspace) / "file.txt"
    test_file.write_text("line 1\nline 2\nline 3\n")

    tool = UnifiedPatchTool()
    patch = (
        "--- a/file.txt\n"
        "+++ b/file.txt\n"
        "@@ -1,3 +1,3 @@\n"
        " line 1\n"
        "-line 2\n"
        "+line two\n"
        " line 3\n"
    )

    result = await tool.execute({"patch": patch}, tool_context)
    assert not result.is_error
    assert "Patch applied successfully" in result.output
    assert test_file.read_text() == "line 1\nline two\nline 3\n"

@pytest.mark.asyncio
async def test_unified_patch_tool_create_file(temp_workspace, tool_context):
    tool = UnifiedPatchTool()
    patch = (
        "--- /dev/null\n"
        "+++ b/created.txt\n"
        "@@ -0,0 +1,2 @@\n"
        "+first line\n"
        "+second line\n"
    )

    result = await tool.execute({"patch": patch}, tool_context)
    assert not result.is_error
    new_file = Path(temp_workspace) / "created.txt"
    assert new_file.exists()
    assert new_file.read_text() == "first line\nsecond line\n"

@pytest.mark.asyncio
async def test_unified_patch_tool_path_traversal(temp_workspace, tool_context):
    tool = UnifiedPatchTool()
    patch = (
        "--- a/../secret.txt\n"
        "+++ b/../secret.txt\n"
        "@@ -1,1 +1,1 @@\n"
        "-old\n"
        "+new\n"
    )

    result = await tool.execute({"patch": patch}, tool_context)
    assert result.is_error
    assert "outside of workspace" in result.output

@pytest.mark.asyncio
async def test_unified_patch_tool_protected_file(temp_workspace, tool_context):
    tool = UnifiedPatchTool()
    patch = (
        "--- a/protected.txt\n"
        "+++ b/protected.txt\n"
        "@@ -1,1 +1,1 @@\n"
        "-old\n"
        "+new\n"
    )

    result = await tool.execute({"patch": patch}, tool_context)
    assert result.is_error
    assert "Archivo protegido" in result.output

@pytest.mark.asyncio
async def test_unified_patch_tool_untrusted(temp_workspace, tool_context):
    tool = UnifiedPatchTool()
    tool_context.trusted = False
    patch = (
        "--- a/file.txt\n"
        "+++ b/file.txt\n"
        "@@ -1,1 +1,1 @@\n"
        "-old\n"
        "+new\n"
    )

    result = await tool.execute({"patch": patch}, tool_context)
    assert result.is_error
    assert "no confiado" in result.output

@pytest.mark.asyncio
async def test_unified_patch_tool_outdated_context(temp_workspace, tool_context):
    test_file = Path(temp_workspace) / "file.txt"
    test_file.write_text("line A\nline B\nline C\n")

    tool = UnifiedPatchTool()
    patch = (
        "--- a/file.txt\n"
        "+++ b/file.txt\n"
        "@@ -1,3 +1,3 @@\n"
        " line A\n"
        "-line NON_EXISTENT\n"
        "+line replaced\n"
        " line C\n"
    )

    result = await tool.execute({"patch": patch}, tool_context)
    assert result.is_error
    assert "Error checking patch" in result.output
    # Detailed line error check from git apply
    assert "patch failed" in result.output or "file.txt" in result.output
