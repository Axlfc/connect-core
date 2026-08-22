import os
import tempfile
from pathlib import Path
import pytest

from app.core.fs_observation_policy import FSObservationPolicy, GENERIC_ACCESS_ERROR
from app.core.tools.base import ToolContext
from app.core.tools.read_tool import ReadTool
from app.core.tools.fs_tools import ListDirectoryTool, SearchFilesTool


@pytest.fixture
def workspace_env():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir).resolve()

        # Create normal files & dirs
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("print('hello')")
        (tmp_path / "readme.txt").write_text("Hello world")

        # Create hidden/ignored files & dirs
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "config").write_text("git config")
        (tmp_path / ".env").write_text("SECRET=123")
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "package.json").write_text("{}")
        (tmp_path / "dashboard.html").write_text("<html>dashboard</html>")
        (tmp_path / "secret.log").write_text("log data")

        # Create .gitignore
        (tmp_path / ".gitignore").write_text("*.log\ncustom_ignored/\n")
        (tmp_path / "custom_ignored").mkdir()
        (tmp_path / "custom_ignored" / "data.txt").write_text("ignored")

        yield tmp_path


@pytest.fixture
def tool_context(workspace_env):
    return ToolContext(
        cwd=str(workspace_env),
        trusted=True,
        protected_files={"dashboard.html", "assets/javascript/auth.js"},
    )


def test_default_exclusions_and_gitignore(workspace_env):
    policy = FSObservationPolicy(
        cwd=workspace_env,
        protected_files={"dashboard.html"},
    )

    # Allowed paths
    assert not policy.is_path_ignored("readme.txt")
    assert not policy.is_path_ignored("src/main.py")

    # Default ignored paths
    assert policy.is_path_ignored(".env")
    assert policy.is_path_ignored(".git")
    assert policy.is_path_ignored(".git/config")
    assert policy.is_path_ignored("node_modules")
    assert policy.is_path_ignored("node_modules/package.json")

    # Protected files
    assert policy.is_path_ignored("dashboard.html")

    # .gitignore rules
    assert policy.is_path_ignored("secret.log")
    assert policy.is_path_ignored("custom_ignored/data.txt")


def test_path_traversal_protection(workspace_env):
    policy = FSObservationPolicy(cwd=workspace_env)

    assert policy.is_path_ignored("../outside.txt")
    assert policy.is_path_ignored("../../etc/passwd")
    assert policy.is_path_ignored("/etc/passwd")


@pytest.mark.asyncio
async def test_read_tool_proactive_filtering(workspace_env, tool_context):
    tool = ReadTool()

    # Allowed file read
    res_ok = await tool.execute({"path": "readme.txt"}, tool_context)
    assert not res_ok.is_error
    assert res_ok.output == "Hello world"

    # Reading .env -> generic error
    res_env = await tool.execute({"path": ".env"}, tool_context)
    assert res_env.is_error
    assert res_env.output == GENERIC_ACCESS_ERROR

    # Reading .git/config -> generic error
    res_git = await tool.execute({"path": ".git/config"}, tool_context)
    assert res_git.is_error
    assert res_git.output == GENERIC_ACCESS_ERROR

    # Reading protected dashboard.html -> generic error
    res_prot = await tool.execute({"path": "dashboard.html"}, tool_context)
    assert res_prot.is_error
    assert res_prot.output == GENERIC_ACCESS_ERROR

    # Path traversal read -> generic error
    res_trav = await tool.execute({"path": "../outside.txt"}, tool_context)
    assert res_trav.is_error
    assert res_trav.output == GENERIC_ACCESS_ERROR


@pytest.mark.asyncio
async def test_list_directory_tool_proactive_filtering(workspace_env, tool_context):
    tool = ListDirectoryTool()

    result = await tool.execute({"path": "."}, tool_context)
    assert not result.is_error

    lines = result.output.splitlines()
    assert "[FILE] readme.txt" in lines
    assert "[DIR] src" in lines

    # Ensured hidden files are not present in output
    assert "[FILE] .env" not in lines
    assert "[DIR] .git" not in lines
    assert "[DIR] node_modules" not in lines
    assert "[FILE] dashboard.html" not in lines
    assert "[FILE] secret.log" not in lines
    assert "[DIR] custom_ignored" not in lines

    # Listing an ignored directory directly returns generic error
    res_git_dir = await tool.execute({"path": ".git"}, tool_context)
    assert res_git_dir.is_error
    assert res_git_dir.output == GENERIC_ACCESS_ERROR


@pytest.mark.asyncio
async def test_search_files_tool_proactive_filtering(workspace_env, tool_context):
    tool = SearchFilesTool()

    result = await tool.execute({"pattern": "*"}, tool_context)
    assert not result.is_error

    matches = result.output.splitlines()
    assert "readme.txt" in matches
    assert "src/main.py" in matches

    # Excluded files must not be in search results
    assert ".env" not in matches
    assert ".git/config" not in matches
    assert "dashboard.html" not in matches
    assert "secret.log" not in matches
    assert "node_modules/package.json" not in matches
