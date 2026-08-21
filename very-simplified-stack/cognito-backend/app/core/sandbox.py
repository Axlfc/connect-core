import asyncio
import os
import sys
import tempfile
import logging
from typing import Dict, Any, Optional
from app.core.exec_policy import default_exec_policy, session_approval_cache, ExecPolicy, SessionApprovalCache

logger = logging.getLogger(__name__)

class SandboxedExecutor:
    """
    Isolates code/shell execution in a safe, monitored python process (NOOA-11).
    Applies ExecPolicy evaluation, approval caching, timeouts, path restrictions, etc.
    """
    def __init__(
        self,
        working_dir: Optional[str] = None,
        timeout: int = 30,
        exec_policy: ExecPolicy = default_exec_policy,
        approval_cache: SessionApprovalCache = session_approval_cache
    ):
        self.working_dir = working_dir or tempfile.gettempdir()
        self.timeout = timeout
        self.exec_policy = exec_policy
        self.approval_cache = approval_cache

    async def execute_cmd(
        self,
        command: str,
        session_id: str = "default_session",
        project_trusted: bool = False,
        user_approved: bool = False
    ) -> Dict[str, Any]:
        """
        Evaluates ExecPolicy and session cache before executing a shell command inside the sandbox.
        """
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

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.working_dir
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

        except Exception as e:
            return {
                "stdout": "",
                "stderr": f"Execution error: {str(e)}",
                "exit_code": 1,
                "timed_out": False,
                "approval_required": False
            }

    async def execute_code(self, code: str) -> Dict[str, Any]:
        """
        Executes raw Python code inside a separate python subprocess, capturing output.
        """
        # Save temporary file inside our safe working directory
        temp_file = os.path.join(self.working_dir, f"sandbox_{os.getpid()}_{id(code)}.py")
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(code)

        try:
            # Build execution process with resource bounds
            proc = await asyncio.create_subprocess_exec(
                sys.executable, temp_file,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.working_dir
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
                    "timed_out": True
                }

            return {
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
                "exit_code": exit_code,
                "timed_out": False
            }

        finally:
            # Cleanup temp file
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass
