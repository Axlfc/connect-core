import os
import shutil
import pytest
from pathlib import Path
from unittest.mock import patch

import app.core.sandbox as sandbox_module
from app.core.sandbox import (
    is_bwrap_available,
    build_bwrap_args,
    SandboxedExecutor,
    SandboxUnavailableError,
)

requires_bwrap = pytest.mark.skipif(
    shutil.which("bwrap") is None,
    reason="Bubblewrap (bwrap) binary is not installed on host."
)


def test_build_bwrap_args_includes_clearenv():
    cwd = Path("/tmp/test_workspace")
    args = build_bwrap_args(cwd=cwd)

    assert "--clearenv" in args
    assert "--share-net" not in args


def test_build_safe_env():
    build_safe_env = getattr(sandbox_module, "build_safe_env", None)
    assert build_safe_env is not None

    with patch.dict(os.environ, {"SECRET_TOKEN_ENV": "SUPER_SECRET", "PATH": "/bin:/usr/bin"}):
        safe_env = build_safe_env()
        assert "SECRET_TOKEN_ENV" not in safe_env
        assert "PATH" in safe_env


@requires_bwrap
@pytest.mark.asyncio
async def test_sandbox_env_leak_prevention(tmp_path, monkeypatch):
    monkeypatch.setenv("HOST_SECRET_VAR", "LEAKED_SECRET_VALUE")
    executor = SandboxedExecutor(working_dir=str(tmp_path), timeout=10)

    res = await executor.execute_cmd("env")
    assert res["exit_code"] == 0
    assert "HOST_SECRET_VAR" not in res["stdout"]


@requires_bwrap
@pytest.mark.asyncio
async def test_sandbox_home_directory_hidden(tmp_path, monkeypatch):
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    ssh_dir = fake_home / ".ssh"
    ssh_dir.mkdir()
    secret_file = ssh_dir / "id_rsa"
    secret_file.write_text("SUPER_SECRET_KEY", encoding="utf-8")

    monkeypatch.setenv("HOME", str(fake_home))
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    executor = SandboxedExecutor(working_dir=str(workspace), timeout=10)

    # Attempt to read secret file in home
    res = await executor.execute_cmd(f"cat {secret_file}")
    assert res["exit_code"] != 0 or "SUPER_SECRET_KEY" not in res["stdout"]


@requires_bwrap
@pytest.mark.asyncio
async def test_sandbox_resource_limits_memory(tmp_path):
    executor = SandboxedExecutor(working_dir=str(tmp_path), timeout=10)

    code = (
        "import os\n"
        "try:\n"
        "    bytearray(300 * 1024 * 1024)\n"
        "    print('ALLOCATED')\n"
        "except MemoryError:\n"
        "    print('MEMORY_ERROR')\n"
    )

    with patch.dict(os.environ, {"COGNITO_SANDBOX_MEMORY_MB": "50"}):
        res = await executor.execute_code(code)
        assert "ALLOCATED" not in res["stdout"]


@requires_bwrap
@pytest.mark.asyncio
async def test_sandbox_timeout_reaps_process(tmp_path):
    executor = SandboxedExecutor(working_dir=str(tmp_path), timeout=1)

    res = await executor.execute_cmd("sleep 10")
    assert res["timed_out"] is True
    assert res["exit_code"] == -1


def test_docker_compose_no_plaintext_passwords():
    repo_root = Path(__file__).parents[3]
    compose_paths = [
        repo_root / "docker-compose.yml",
        repo_root / "very-simplified-stack" / "docker-compose.yml",
    ]

    for compose_path in compose_paths:
        if not compose_path.exists():
            continue

        content = compose_path.read_text(encoding="utf-8")
        assert ":-admin_password" not in content, f"Found plain text default password in {compose_path}"
        assert ":-redis_password" not in content, f"Found plain text default password in {compose_path}"
