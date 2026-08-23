import asyncio
import os
import sys
import shutil
import tempfile
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from app.core.exec_policy import default_exec_policy, session_approval_cache, ExecPolicy, SessionApprovalCache

logger = logging.getLogger(__name__)


class SandboxUnavailableError(RuntimeError):
    """
    Exception raised when bubblewrap ('bwrap') is not installed or available on the host system.
    """
    pass


def is_bwrap_available() -> bool:
    """
    Checks if bubblewrap ('bwrap') binary is available on the host system.
    """
    return shutil.which("bwrap") is not None


def build_bwrap_args(cwd: Path, allowed_network: bool = False) -> List[str]:
    """
    Builds bubblewrap execution arguments for sandbox isolation.
    - Mounts root filesystem as read-only (--ro-bind / /).
    - Mounts working directory with write permissions (--bind {cwd} {cwd}).
    - Unshares all namespaces for process isolation (--unshare-all --die-with-parent).
    - Conditionally enables network access (--share-net).
    """
    cwd_path = Path(cwd).resolve()
    cwd_str = str(cwd_path)

    args = [
        "bwrap",
        "--ro-bind", "/", "/",
        "--bind", cwd_str, cwd_str,
        "--unshare-all",
        "--die-with-parent"
    ]

    if allowed_network:
        args.append("--share-net")

    return args


class SandboxedExecutor:
    """
    Isolates code/shell execution in a safe, monitored python process (NOOA-11).
    Applies ExecPolicy evaluation, approval caching, timeouts, path restrictions, etc.
    """
    def __init__(
        self,
        working_dir: Optional[str] = None,
        timeout: int = 30,
        allowed_network: bool = False,
        exec_policy: ExecPolicy = default_exec_policy,
        approval_cache: SessionApprovalCache = session_approval_cache
    ):
        self.working_dir = working_dir or tempfile.gettempdir()
        self.timeout = timeout
        self.allowed_network = allowed_network
        self.exec_policy = exec_policy
        self.approval_cache = approval_cache

    async def _verify_bwrap(self) -> None:
        """
        Verifies that bubblewrap ('bwrap') is available. If not, logs a CRITICAL security error
        and raises SandboxUnavailableError.
        """
        if not is_bwrap_available():
            msg = (
                "Error de Seguridad: Bubblewrap (bwrap) no está instalado en el host. "
                "La ejecución de código no está aislada. Instala bwrap o contacta al administrador."
            )
            logger.critical(msg)
            raise SandboxUnavailableError(msg)

    async def execute_cmd(
        self,
        command: str,
        session_id: str = "default_session",
        project_trusted: bool = False,
        user_approved: bool = False
    ) -> Dict[str, Any]:
        """
        Evaluates ExecPolicy and session cache before executing a shell command inside the sandbox.
        Requires bwrap to be installed; raises SandboxUnavailableError if missing.
        """
        await self._verify_bwrap()

        is_cache_approved = self.approval_cache.is_approved(session_id, command)

        if user_approved:
            self.approval_cache.approve(session_id, command)

        auto_approved = is_cache_approved or user_approved

        if not auto_approved:
            if self.exec_policy.requires_explicit_approval(command, project_trusted=project_trusted):
                return {
                    "stdout": "",
                    "stderr": f"ExecPolicy: Command '{command}' requires explicit approval.",
                    "exit_code": 1,
                    "timed_out": False,
                    "approval_required": True
                }

        cwd_path = Path(self.working_dir).resolve()
        cmd = build_bwrap_args(cwd=cwd_path, allowed_network=self.allowed_network) + ["sh", "-c", command]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd_path
            )

            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self.timeout)
                return {
                    "stdout": stdout.decode("utf-8", errors="replace"),
                    "stderr": stderr.decode("utf-8", errors="replace"),
                    "exit_code": proc.returncode,
                    "timed_out": False,
                    "approval_required": False
                }
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
                return {
                    "stdout": "",
                    "stderr": "Execution timed out.",
                    "exit_code": -1,
                    "timed_out": True,
                    "approval_required": False
                }

        except SandboxUnavailableError:
            raise
        except Exception as e:
            return {
                "stdout": "",
                "stderr": f"Execution error: {str(e)}",
                "exit_code": 1,
                "timed_out": False,
                "approval_required": False
            }

    async def execute_code(self, code: str, allowed_network: Optional[bool] = None) -> Dict[str, Any]:
        """
        Executes raw Python code inside a separate python subprocess wrapped in bubblewrap (bwrap).
        Requires bwrap to be installed; raises SandboxUnavailableError if missing.
        """
        await self._verify_bwrap()

        net_allowed = self.allowed_network if allowed_network is None else allowed_network
        cwd_path = Path(self.working_dir).resolve()

        # Save temporary file inside our safe working directory
        temp_file = cwd_path / f"sandbox_{os.getpid()}_{id(code)}.py"
        temp_file.write_text(code, encoding="utf-8")

        cmd = build_bwrap_args(cwd=cwd_path, allowed_network=net_allowed) + [sys.executable, str(temp_file)]
        context = "bwrap"

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd_path
            )

            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self.timeout)
                exit_code = proc.returncode
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
                return {
                    "stdout": "",
                    "stderr": "Execution timed out.",
                    "exit_code": -1,
                    "timed_out": True,
                    "context": context
                }

            return {
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
                "exit_code": exit_code,
                "timed_out": False,
                "context": context
            }

        finally:
            # Cleanup temp file
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass
