import os
import re
import shutil
import pytest
from pathlib import Path
from unittest.mock import patch

import app.core.sandbox as sandbox_module
from app.core.sandbox import (
    is_bwrap_available,
    build_bwrap_args,
    get_prlimit_prefix,
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


def test_get_prlimit_prefix_no_nproc():
    prefix = get_prlimit_prefix()
    prefix_str = " ".join(prefix)

    # --nproc must NOT be in prlimit options
    assert "--nproc" not in prefix_str
    if prefix:
        assert "prlimit" in prefix[0]
        assert any("--cpu=" in item for item in prefix)
        assert any("--as=" in item for item in prefix)
        assert any("--nofile=" in item for item in prefix)


def test_build_bwrap_args_home_slash_or_nonexistent():
    # Test HOME="/"
    with patch.dict(os.environ, {"HOME": "/"}):
        args_slash = build_bwrap_args(cwd=Path("/tmp/ws"))
        tmpfs_targets = [args_slash[i+1] for i in range(len(args_slash)-1) if args_slash[i] == "--tmpfs"]
        assert "/" not in tmpfs_targets

    # Test HOME non-existent directory
    with patch.dict(os.environ, {"HOME": "/nonexistent_path_xyz_12345"}):
        args_nonexist = build_bwrap_args(cwd=Path("/tmp/ws"))
        assert "/nonexistent_path_xyz_12345" not in args_nonexist


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
async def test_sandbox_worktree_under_home(tmp_path, monkeypatch):
    fake_home = tmp_path / "home_user"
    fake_home.mkdir()
    gitdir = fake_home / ".cognito" / "worktrees" / "main_repo" / "gitdir"
    gitdir.mkdir(parents=True)
    (gitdir / "HEAD").write_text("ref: refs/heads/master\n", encoding="utf-8")

    monkeypatch.setenv("HOME", str(fake_home))

    worktree_dir = tmp_path / "wt_workspace"
    worktree_dir.mkdir()
    (worktree_dir / ".git").write_text(f"gitdir: {gitdir}\n", encoding="utf-8")

    args = build_bwrap_args(cwd=worktree_dir)
    # Check that gitdir path is re-exposed via --ro-bind
    assert str(gitdir) in args


@requires_bwrap
@pytest.mark.asyncio
async def test_sandbox_cwd_under_tmp_writable(tmp_path):
    executor = SandboxedExecutor(working_dir=str(tmp_path), timeout=10)

    res = await executor.execute_cmd("echo 'WRITTEN_IN_TMP' > test_file.txt")
    assert res["exit_code"] == 0

    created_file = tmp_path / "test_file.txt"
    assert created_file.exists()
    assert "WRITTEN_IN_TMP" in created_file.read_text(encoding="utf-8")


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
        assert "ALLOCATED" not in res["stdout"], "Memory limit failed: 300MB allocation succeeded under 50MB limit"


@requires_bwrap
@pytest.mark.asyncio
async def test_sandbox_timeout_reaps_process(tmp_path):
    executor = SandboxedExecutor(working_dir=str(tmp_path), timeout=1)

    res = await executor.execute_cmd("sleep 10")
    assert res["timed_out"] is True
    assert res["exit_code"] == -1


def test_docker_compose_no_plaintext_sensitive_fallbacks():
    repo_root = Path(__file__).parents[3]
    compose_paths = [
        repo_root / "docker-compose.yml",
        repo_root / "very-simplified-stack" / "docker-compose.yml",
    ]

    sensitive_regex = re.compile(r'\$\{([A-Z0-9_]*(?:PASSWORD|SECRET|TOKEN|KEY)[A-Z0-9_]*):-[^}]+\}')

    for compose_path in compose_paths:
        if not compose_path.exists():
            continue

        content = compose_path.read_text(encoding="utf-8")
        matches = sensitive_regex.findall(content)
        assert not matches, f"Found plain text default fallback for sensitive variable(s) {matches} in {compose_path}"


def test_docker_compose_ports_bound_to_localhost():
    stack_compose = Path(__file__).parents[2] / "docker-compose.yml"
    assert stack_compose.exists()

    content = stack_compose.read_text(encoding="utf-8")
    assert "127.0.0.1:6333:6333" in content
    assert "127.0.0.1:8000:8000" in content
