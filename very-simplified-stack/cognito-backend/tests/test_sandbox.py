import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock
from app.core.sandbox import (
    is_bwrap_available,
    build_bwrap_args,
    get_sandbox_allowed_hosts,
    is_host_allowed,
    SandboxedExecutor,
    SandboxUnavailableError,
    SandboxNetworkError,
)


def test_is_bwrap_available():
    with patch("shutil.which", return_value="/usr/bin/bwrap"):
        assert is_bwrap_available() is True

    with patch("shutil.which", return_value=None):
        assert is_bwrap_available() is False


def test_build_bwrap_args_deny_all_by_default():
    cwd = Path("/tmp/test_workspace")
    args = build_bwrap_args(cwd=cwd, allowed_network=False)

    assert args[0] == "bwrap"
    assert "--ro-bind" in args
    assert "/" in args
    assert "--dev" in args
    assert "/dev" in args
    assert "--proc" in args
    assert "/proc" in args
    assert "--tmpfs" in args
    assert "/tmp" in args
    assert "--bind" in args
    assert str(cwd.resolve()) in args
    assert "--unshare-all" in args
    assert "--die-with-parent" in args
    assert "--share-net" not in args

    # --share-net MUST NEVER be added regardless of parameters (strict kernel namespace deny-all isolation)
    args_net_no_target = build_bwrap_args(cwd=cwd, allowed_network=True)
    assert "--share-net" not in args_net_no_target

    args_net_whitelisted = build_bwrap_args(cwd=cwd, allowed_network=True, target_host="127.0.0.1")
    assert "--share-net" not in args_net_whitelisted

    args_net_unwhitelisted = build_bwrap_args(cwd=cwd, allowed_network=True, target_host="forbidden-evil-domain.com")
    assert "--share-net" not in args_net_unwhitelisted


def test_get_sandbox_allowed_hosts_and_is_host_allowed(monkeypatch):
    monkeypatch.setenv("COGNITO_SANDBOX_ALLOWED_HOSTS", "custom-api.domain.com, 10.200.0.15:8080")

    hosts = get_sandbox_allowed_hosts()

    assert "localhost" in hosts
    assert "127.0.0.1" in hosts
    assert "host.docker.internal" in hosts
    assert "custom-api.domain.com" in hosts
    assert "10.200.0.15" in hosts

    # Whitelisted hosts pass check
    assert is_host_allowed("localhost") is True
    assert is_host_allowed("127.0.0.1") is True
    assert is_host_allowed("http://custom-api.domain.com/v1") is True
    assert is_host_allowed("10.200.0.15:8080") is True

    # Unlisted hosts fail check
    assert is_host_allowed("arbitrary-internet-host.com") is False
    assert is_host_allowed("8.8.8.8") is False
    assert is_host_allowed("https://malicious-site.org/exfiltrate") is False


@pytest.mark.asyncio
async def test_sandboxed_executor_unwhitelisted_host_fails():
    executor = SandboxedExecutor(working_dir="/tmp", target_host="malicious-site.org")

    with patch("app.core.sandbox.is_bwrap_available", return_value=True):
        with pytest.raises(SandboxNetworkError) as exc_info:
            await executor.execute_cmd("curl https://malicious-site.org")
        assert "Acceso de red denegado" in str(exc_info.value)
        assert "malicious-site.org" in str(exc_info.value)

        with pytest.raises(SandboxNetworkError) as exc_info_code:
            await executor.execute_code("import urllib.request; urllib.request.urlopen('https://malicious-site.org')")
        assert "Acceso de red denegado" in str(exc_info_code.value)


@pytest.mark.asyncio
async def test_sandboxed_executor_raises_when_bwrap_unavailable():
    with patch("app.core.sandbox.is_bwrap_available", return_value=False), \
         patch("app.core.sandbox.logger.critical") as mock_log:

        executor = SandboxedExecutor()

        with pytest.raises(SandboxUnavailableError) as exc_info:
            await executor.execute_code("print('bwrap test')")

        expected_msg = (
            "Error de Seguridad: Bubblewrap (bwrap) no está instalado en el host. "
            "La ejecución de código no está aislada. Instala bwrap o contacta al administrador."
        )
        assert expected_msg in str(exc_info.value)

        with pytest.raises(SandboxUnavailableError) as exc_info_cmd:
            await executor.execute_cmd("echo test")

        assert expected_msg in str(exc_info_cmd.value)
        mock_log.assert_called()


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


@pytest.mark.asyncio
async def test_bash_tool_mandatory_sandbox_by_default(monkeypatch, tmp_path):
    from app.core.tools.bash_tool import BashTool
    from app.core.tools.base import ToolContext

    monkeypatch.delenv("COGNITO_DISABLE_SANDBOX_DEV_ONLY", raising=False)
    tool = BashTool()
    ctx = ToolContext(cwd=str(tmp_path), trusted=True, protected_files=set())

    with patch("app.core.sandbox.is_bwrap_available", return_value=True), \
         patch("app.core.sandbox.SandboxedExecutor.execute_cmd") as mock_exec_cmd:
        mock_exec_cmd.return_value = {
            "stdout": "sandboxed output",
            "stderr": "",
            "exit_code": 0,
            "timed_out": False
        }
        res = await tool.execute({"command": "echo hello"}, ctx)
        assert res.is_error is False
        assert "sandboxed output" in res.output
        mock_exec_cmd.assert_called_once()


@pytest.mark.asyncio
async def test_bash_tool_bwrap_unavailable_error(monkeypatch, tmp_path):
    from app.core.tools.bash_tool import BashTool
    from app.core.tools.base import ToolContext

    monkeypatch.delenv("COGNITO_DISABLE_SANDBOX_DEV_ONLY", raising=False)
    tool = BashTool()
    ctx = ToolContext(cwd=str(tmp_path), trusted=True, protected_files=set())

    with patch("app.core.sandbox.is_bwrap_available", return_value=False):
        res = await tool.execute({"command": "echo hello"}, ctx)
        assert res.is_error is True
        assert "Error de Seguridad: Bubblewrap (bwrap) no está instalado" in res.output


@pytest.mark.asyncio
async def test_bash_tool_dev_bypass_warning(monkeypatch, tmp_path):
    from app.core.tools.bash_tool import BashTool
    from app.core.tools.base import ToolContext

    monkeypatch.setenv("COGNITO_DISABLE_SANDBOX_DEV_ONLY", "true")
    tool = BashTool()
    ctx = ToolContext(cwd=str(tmp_path), trusted=True, protected_files=set())

    with patch("app.core.sandbox.logger.warning") as mock_warn, \
         patch("asyncio.create_subprocess_shell") as mock_subproc:

        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"direct host output\n", b"")
        mock_proc.returncode = 0
        mock_subproc.return_value = mock_proc

        res = await tool.execute({"command": "echo bypass"}, ctx)
        assert res.is_error is False
        assert "direct host output" in res.output
        mock_warn.assert_called()
        assert "DESACTIVADO" in mock_warn.call_args[0][0]


@pytest.mark.asyncio
async def test_real_bwrap_isolation_network(tmp_path):
    """
    Test that a command executed via SandboxedExecutor/bwrap has ZERO network connectivity,
    failing at network/socket level even when attempting to reach whitelisted hosts (127.0.0.1 / localhost).
    """
    from app.core.sandbox import is_bwrap_available, SandboxedExecutor
    if not is_bwrap_available():
        pytest.skip("bwrap binary not installed on host system")

    executor = SandboxedExecutor(working_dir=str(tmp_path), timeout=10)

    # Attempt active socket connection to whitelisted local address inside bwrap sandbox
    code = (
        "import socket\n"
        "try:\n"
        "    s = socket.create_connection(('127.0.0.1', 8080), timeout=1)\n"
        "    print('CONNECTED')\n"
        "except Exception as e:\n"
        "    print(f'NETWORK_FAILED: {e}')\n"
    )

    res = await executor.execute_code(code, target_host="127.0.0.1")
    assert res["exit_code"] == 0
    assert "NETWORK_FAILED" in res["stdout"]
    assert "CONNECTED" not in res["stdout"]


@pytest.mark.asyncio
async def test_real_bwrap_isolation_filesystem(tmp_path):
    """
    Test that within real bwrap sandbox, a command cannot read or write outside allowed working dir.
    """
    from app.core.sandbox import is_bwrap_available, SandboxedExecutor
    if not is_bwrap_available():
        pytest.skip("bwrap binary not installed on host system")

    allowed_dir = tmp_path / "allowed_workspace"
    allowed_dir.mkdir()

    executor = SandboxedExecutor(working_dir=str(allowed_dir), timeout=10)

    # 1. Allowed directory write & read
    res1 = await executor.execute_cmd("echo 'inside' > allowed_file.txt && cat allowed_file.txt", project_trusted=True, user_approved=True)
    assert res1["exit_code"] == 0
    assert "inside" in res1["stdout"]

    # 2. Attempt write outside working dir (e.g. /home or /var)
    res2 = await executor.execute_cmd("touch /home/forbidden_test_file.txt", project_trusted=True, user_approved=True)
    assert res2["exit_code"] != 0
    assert "Read-only file system" in res2["stderr"] or "Permission denied" in res2["stderr"]

    # 3. Write in /tmp should be isolated via tmpfs and not alter host /tmp
    res3 = await executor.execute_cmd("echo 'isolated' > /tmp/isolated_test.txt && cat /tmp/isolated_test.txt", project_trusted=True, user_approved=True)
    assert res3["exit_code"] == 0
    assert "isolated" in res3["stdout"]
    assert not Path("/tmp/isolated_test.txt").exists()
