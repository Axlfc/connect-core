import os
import tempfile
import asyncio
import pytest
from app.core.tools.code_review_tool import CodeReviewTool, REVIEW_PROMPT_HEADER
from app.core.tools.base import ToolContext
from app.core.extensions.registry import extension_registry


@pytest.fixture
def tool_context(tmp_path):
    return ToolContext(cwd=str(tmp_path), trusted=True, protected_files=set())


async def run_git(cwd, *args):
    proc = await asyncio.create_subprocess_exec("git", *args, cwd=cwd)
    await proc.communicate()


@pytest.mark.asyncio
async def test_code_review_tool_uncommitted(tmp_path):
    cwd = str(tmp_path)
    # Init git repo
    await run_git(cwd, "init")
    await run_git(cwd, "config", "user.name", "Test User")
    await run_git(cwd, "config", "user.email", "test@example.com")

    # Initial commit
    file1 = tmp_path / "hello.py"
    file1.write_text("print('hello')\n")
    await run_git(cwd, "add", "hello.py")
    await run_git(cwd, "commit", "-m", "initial commit")

    # Make uncommitted change
    file1.write_text("print('hello world')\n")

    tool = CodeReviewTool()
    ctx = ToolContext(cwd=cwd, trusted=True, protected_files=set())

    result = await tool.execute({"target": "uncommitted"}, ctx)
    assert not result.is_error
    assert REVIEW_PROMPT_HEADER in result.output
    assert "print('hello world')" in result.output
    assert "uncommitted" in result.output.lower()


@pytest.mark.asyncio
async def test_code_review_tool_branch(tmp_path):
    cwd = str(tmp_path)
    await run_git(cwd, "init")
    await run_git(cwd, "config", "user.name", "Test User")
    await run_git(cwd, "config", "user.email", "test@example.com")

    # Initial commit on main
    file1 = tmp_path / "main.py"
    file1.write_text("v1\n")
    await run_git(cwd, "add", "main.py")
    await run_git(cwd, "commit", "-m", "main commit")
    await run_git(cwd, "branch", "-M", "main")

    # Create feature branch
    await run_git(cwd, "checkout", "-b", "feature")
    file1.write_text("v2\n")
    await run_git(cwd, "commit", "-am", "feature commit")

    tool = CodeReviewTool()
    ctx = ToolContext(cwd=cwd, trusted=True, protected_files=set())

    result = await tool.execute({"target": "branch:main"}, ctx)
    assert not result.is_error
    assert REVIEW_PROMPT_HEADER in result.output
    assert "-v1" in result.output or "+v2" in result.output


@pytest.mark.asyncio
async def test_code_review_tool_commit(tmp_path):
    cwd = str(tmp_path)
    await run_git(cwd, "init")
    await run_git(cwd, "config", "user.name", "Test User")
    await run_git(cwd, "config", "user.email", "test@example.com")

    file1 = tmp_path / "app.py"
    file1.write_text("def main(): pass\n")
    await run_git(cwd, "add", "app.py")
    await run_git(cwd, "commit", "-m", "first commit")

    file1.write_text("def main(): return 42\n")
    await run_git(cwd, "commit", "-am", "second commit")

    # Get latest commit hash
    proc = await asyncio.create_subprocess_exec(
        "git", "rev-parse", "HEAD", cwd=cwd, stdout=asyncio.subprocess.PIPE
    )
    stdout, _ = await proc.communicate()
    commit_hash = stdout.decode().strip()

    tool = CodeReviewTool()
    ctx = ToolContext(cwd=cwd, trusted=True, protected_files=set())

    result = await tool.execute({"target": f"commit:{commit_hash}"}, ctx)
    assert not result.is_error
    assert REVIEW_PROMPT_HEADER in result.output
    assert "return 42" in result.output


@pytest.mark.asyncio
async def test_code_review_tool_truncation(tmp_path):
    cwd = str(tmp_path)
    await run_git(cwd, "init")
    await run_git(cwd, "config", "user.name", "Test User")
    await run_git(cwd, "config", "user.email", "test@example.com")

    large_file = tmp_path / "large.txt"
    large_file.write_text("a" * 5000 + "\n")
    await run_git(cwd, "add", "large.txt")
    await run_git(cwd, "commit", "-m", "add large file")

    large_file.write_text("b" * 5000 + "\n")

    tool = CodeReviewTool()
    ctx = ToolContext(cwd=cwd, trusted=True, protected_files=set())

    result = await tool.execute({"target": "uncommitted", "max_characters": 200}, ctx)
    assert not result.is_error
    assert "TRUNCATED" in result.output
    assert "SUMMARY OF STATS" in result.output


@pytest.mark.asyncio
async def test_code_review_tool_invalid_target_injection(tmp_path):
    cwd = str(tmp_path)
    await run_git(cwd, "init")
    tool = CodeReviewTool()
    ctx = ToolContext(cwd=cwd, trusted=True, protected_files=set())

    result = await tool.execute({"target": "--bad-arg"}, ctx)
    assert result.is_error
    assert "cannot start with '-'" in result.output


def test_code_review_registered_in_extension_registry(tmp_path):
    tools = extension_registry.tools_for(str(tmp_path))
    tool_names = [t.name for t in tools]
    assert "code_review" in tool_names
