import tempfile
import pytest
from pathlib import Path
from app.core.fs_observation_policy import FSObservationPolicy
from app.core.tools.read_tool import ReadTool
from app.core.tools.list_directory_tool import ListDirectoryTool
from app.core.tools.search_files_tool import SearchFilesTool
from app.core.tools.base import ToolContext

def test_fs_observation_policy_basic():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir).resolve()

        # Create structure
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "config").write_text("git config")
        (tmp_path / ".env").write_text("SECRET=123")
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "pkg.json").write_text("{}")
        (tmp_path / "dashboard.html").write_text("<html></html>")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("print('hello')")
        (tmp_path / ".gitignore").write_text("build/\n*.log\n")
        (tmp_path / "build").mkdir()
        (tmp_path / "build" / "app.out").write_text("binary")
        (tmp_path / "app.log").write_text("logs")

        policy = FSObservationPolicy(cwd=tmp_path, protected_files=["dashboard.html"])

        # Check default hidden paths
        assert policy.is_hidden(".git") is True
        assert policy.is_hidden(".git/config") is True
        assert policy.is_hidden(".env") is True
        assert policy.is_hidden("node_modules") is True
        assert policy.is_hidden("node_modules/pkg.json") is True

        # Check protected files
        assert policy.is_hidden("dashboard.html") is True

        # Check .gitignore patterns
        assert policy.is_hidden("build") is True
        assert policy.is_hidden("build/app.out") is True
        assert policy.is_hidden("app.log") is True

        # Check visible files
        assert policy.is_hidden("src") is False
        assert policy.is_hidden("src/main.py") is False

        # Check path traversal
        assert policy.is_hidden("../outside.txt") is True

        # Filter paths
        paths = ["src/main.py", ".env", "dashboard.html", "app.log"]
        filtered = policy.filter_paths(paths)
        assert filtered == [Path("src/main.py")]

@pytest.mark.asyncio
async def test_fs_tools_proactive_observation():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir).resolve()

        # Create files
        (tmp_path / "visible.py").write_text("print('visible')")
        (tmp_path / ".env").write_text("API_KEY=secret")
        (tmp_path / "dashboard.html").write_text("protected html")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "child.py").write_text("child")
        (tmp_path / "sub" / "hidden.log").write_text("log")
        (tmp_path / ".gitignore").write_text("*.log\n")

        context = ToolContext(
            cwd=str(tmp_path),
            trusted=True,
            protected_files={"dashboard.html"}
        )

        read_tool = ReadTool()
        list_tool = ListDirectoryTool()
        search_tool = SearchFilesTool()

        generic_error = "Archivo o directorio no encontrado o no accesible"

        # Read tool tests
        res_read_ok = await read_tool.execute({"path": "visible.py"}, context)
        assert not res_read_ok.is_error
        assert res_read_ok.output == "print('visible')"

        res_read_env = await read_tool.execute({"path": ".env"}, context)
        assert res_read_env.is_error
        assert res_read_env.output == generic_error

        res_read_prot = await read_tool.execute({"path": "dashboard.html"}, context)
        assert res_read_prot.is_error
        assert res_read_prot.output == generic_error

        res_read_traversal = await read_tool.execute({"path": "../../etc/passwd"}, context)
        assert res_read_traversal.is_error
        assert res_read_traversal.output == generic_error

        # List tool tests
        res_list_root = await list_tool.execute({"path": "."}, context)
        assert not res_list_root.is_error
        assert "visible.py" in res_list_root.output
        assert "sub" in res_list_root.output
        assert ".env" not in res_list_root.output
        assert "dashboard.html" not in res_list_root.output

        # Search tool tests
        res_search = await search_tool.execute({"path": "."}, context)
        assert not res_search.is_error
        assert "visible.py" in res_search.output
        assert "sub/child.py" in res_search.output
        assert ".env" not in res_search.output
        assert "dashboard.html" not in res_search.output
        assert "sub/hidden.log" not in res_search.output
