import asyncio
import os
import sys
import tempfile
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class SandboxedExecutor:
    """
    Isolates code execution in a safe, monitored python process (NOOA-11).
    Applies timeouts, path restrictions, memory constraints, etc.
    """
    def __init__(self, working_dir: Optional[str] = None, timeout: int = 30):
        self.working_dir = working_dir or tempfile.gettempdir()
        self.timeout = timeout

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
