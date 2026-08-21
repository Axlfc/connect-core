import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock
from app.core.sandbox import is_bwrap_available, build_bwrap_args, SandboxedExecutor


def test_is_bwrap_available():
    with patch("shutil.which", return_value="/usr/bin/bwrap"):
        assert is_bwrap_available() is True

    with patch("shutil.which", return_value=None):
        assert is_bwrap_available() is False


def test_build_bwrap_args():
    cwd = Path("/tmp/test_workspace")
    args = build_bwrap_args(cwd=cwd, allowed_network=False)

    assert args[0] == "bwrap"
    assert "--ro-bind" in args
    assert "/" in args
    assert "--bind" in args
    assert str(cwd.resolve()) in args
    assert "--unshare-all" in args
    assert "--die-with-parent" in args
    assert "--share-net" not in args

    args_net = build_bwrap_args(cwd=cwd, allowed_network=True)
    assert "--share-net" in args_net


@pytest.mark.asyncio
async def test_sandboxed_executor_fallback_when_bwrap_unavailable():
    with patch("app.core.sandbox.is_bwrap_available", return_value=False):
        executor = SandboxedExecutor()
        res = await executor.execute_code("print('fallback test')")

        assert res["exit_code"] == 0
        assert "fallback test" in res["stdout"]
        assert res["context"] == "unverified_sandbox"


@pytest.mark.asyncio
async def test_sandboxed_executor_bwrap_command_building():
    with patch("app.core.sandbox.is_bwrap_available", return_value=True), \
         patch("asyncio.create_subprocess_exec") as mock_exec:

        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"bwrap output\n", b"")
        mock_proc.returncode = 0
        mock_exec.return_value = mock_proc

        executor = SandboxedExecutor(working_dir="/tmp", allowed_network=False)
        res = await executor.execute_code("print('bwrap test')")

        assert res["exit_code"] == 0
        assert "bwrap output" in res["stdout"]
        assert res["context"] == "bwrap"

        mock_exec.assert_called_once()
        args = mock_exec.call_args[0]
        assert args[0] == "bwrap"
        assert "--ro-bind" in args
        assert "--bind" in args
        assert "--unshare-all" in args
        assert "--die-with-parent" in args
        assert "--share-net" not in args
