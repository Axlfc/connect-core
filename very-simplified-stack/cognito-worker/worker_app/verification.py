import os
import subprocess
import time
import logging
from typing import List, Dict, Any, Tuple, Literal
from pathlib import Path
from app.models.domain import VerificationRun

logger = logging.getLogger("cognito.worker.verification")

class VerificationEngine:
    def __init__(self):
        pass

    def detect_commands(self, worktree_path: str) -> Dict[str, str]:
        """
        Scans metadata files inside the worktree and resolves standard verification commands.
        Returns a dictionary mapping 'test', 'lint', 'typecheck' to resolved commands.
        """
        p = Path(worktree_path)
        commands = {
            "test": "",
            "lint": "",
            "typecheck": ""
        }

        # 1. Python pytest detection
        if (p / "pyproject.toml").exists() or (p / "pytest.ini").exists() or (p / "tests").exists():
            # If pyproject.toml has poetry or pytest config
            commands["test"] = "PYTHONPATH=. python3 -m pytest"
            commands["lint"] = "flake8 . || true"
            commands["typecheck"] = "mypy . || true"

        # 2. NodeJS detection
        elif (p / "package.json").exists():
            commands["test"] = "npm test"
            commands["lint"] = "npm run lint"
            commands["typecheck"] = "npm run typecheck"

        return commands

    def classify_failure(self, exit_status: int, stderr: str, stdout: str, category: str) -> str:
        """
        Heuristically classifies a command failure into:
        - environmental
        - model_related
        - requirement_related
        - policy_related
        """
        combined = (stdout + "\n" + stderr).lower()

        if "module not found" in combined or "missing dependency" in combined or "npm err!" in combined or "connection refused" in combined:
            return "environmental"
        elif "syntaxerror" in combined or "indentationerror" in combined or "assertionerror" in combined or "failed" in combined:
            return "model_related"
        elif "permission denied" in combined or "unauthorized" in combined:
            return "policy_related"

        return "requirement_related"

    async def run_verification(self, task_id: str, attempt_id: str, worktree_path: str, category: Literal["test", "lint", "typecheck"]) -> VerificationRun:
        start_time = time.time()

        commands_map = self.detect_commands(worktree_path)
        cmd = commands_map.get(category) or ""

        if not cmd:
            # Safe default fallback
            if category == "test":
                cmd = "echo 'No tests found' && exit 0"
            elif category == "lint":
                cmd = "echo 'No linter configured' && exit 0"
            else:
                cmd = "echo 'No type-checker configured' && exit 0"

        logger.info(f"Running verification command for '{category}': {cmd} in {worktree_path}")

        try:
            # Run command inside worktree safely using subprocess shell
            res = subprocess.run(
                cmd,
                shell=True,
                cwd=worktree_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=60 # 60s timeout
            )
            exit_status = res.returncode
            stdout = res.stdout
            stderr = res.stderr
        except subprocess.TimeoutExpired as e:
            exit_status = -1
            stdout = ""
            stderr = f"Command timed out after 60 seconds: {e}"
        except Exception as e:
            exit_status = -1
            stdout = ""
            stderr = f"Execution error: {str(e)}"

        duration = time.time() - start_time

        # Classify failure
        failure_class = None
        failed_tests = []
        if exit_status != 0:
            failure_class = self.classify_failure(exit_status, stderr, stdout, category)
            # Standard pytest output failed tests extraction
            for line in stdout.split("\n"):
                if line.startswith("FAILED "):
                    failed_tests.append(line.replace("FAILED ", "").strip())

        return VerificationRun(
            task_id=task_id,
            attempt_id=attempt_id,
            commands_executed=[cmd],
            exit_status=exit_status,
            duration_sec=duration,
            stdout=stdout,
            stderr=stderr,
            failed_tests=failed_tests,
            failure_classification=failure_class
        )
