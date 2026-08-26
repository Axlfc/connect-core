import asyncio
import os
import re
from typing import Any, Dict
from app.core.tools.base import AgentTool, ToolContext, ToolResult
from app.core.exec_policy import default_exec_policy, session_approval_cache, ExecPolicy, SessionApprovalCache

class BashTool(AgentTool):
    name = "bash"
    description = "Execute a bash command in the current workspace."
    parameters_schema = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "The bash command to execute."},
            "timeout_seconds": {"type": "integer", "description": "Command timeout in seconds.", "default": 30},
            "user_approved": {"type": "boolean", "description": "Explicit user approval flag for execution.", "default": False},
        },
        "required": ["command"],
    }

    def __init__(
        self,
        exec_policy: ExecPolicy = default_exec_policy,
        approval_cache: SessionApprovalCache = session_approval_cache
    ):
        super().__init__()
        self.exec_policy = exec_policy
        self.approval_cache = approval_cache

    async def execute(self, arguments: Dict[str, Any], context: ToolContext) -> ToolResult:
        command = arguments.get("command")
        timeout = min(int(arguments.get("timeout_seconds", 30)), 120)
        user_approved = bool(arguments.get("user_approved", False))
        session_id = getattr(context, "session_id", None) or getattr(context, "task_id", None) or "default_session"

        if not command:
            return ToolResult(is_error=True, output="Error: command is required.")

        from app.core.exec_policy import evaluate_command_execution
        allowed, reason = evaluate_command_execution(
            command=command,
            cwd=context.cwd,
            trusted=context.trusted,
            session_id=session_id,
            user_approved=user_approved,
            exec_policy=self.exec_policy,
            approval_cache=self.approval_cache,
        )

        if not allowed:
            return ToolResult(is_error=True, output=f"Error: {reason}")

        from app.core.sandbox import is_bwrap_available, SandboxedExecutor

        if is_bwrap_available():
            executor = SandboxedExecutor(
                working_dir=context.cwd,
                timeout=timeout,
                allowed_network=getattr(context, "trusted", False),
                exec_policy=self.exec_policy,
                approval_cache=self.approval_cache,
            )
            res = await executor.execute_cmd(
                command=command,
                session_id=session_id,
                project_trusted=context.trusted,
                user_approved=user_approved,
            )
            output = res.get("stdout", "") + res.get("stderr", "")
            return ToolResult(output=output, is_error=res.get("exit_code", 0) != 0)

        # Fallback to direct subprocess with preexec resource limits if bwrap is not available
        import resource

        def _set_limits():
            try:
                # Limit CPU time to 30s
                resource.setrlimit(resource.RLIMIT_CPU, (30, 35))
            except Exception:
                pass
            try:
                # Limit address space to 512MB
                resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
            except Exception:
                pass
            try:
                # Limit max file write size to 50MB
                resource.setrlimit(resource.RLIMIT_FSIZE, (50 * 1024 * 1024, 50 * 1024 * 1024))
            except Exception:
                pass

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=context.cwd,
                preexec_fn=_set_limits
            )

            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
                output = (stdout + stderr).decode("utf-8")
                return ToolResult(output=output, is_error=process.returncode != 0)
            except asyncio.TimeoutError:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
                return ToolResult(is_error=True, output=f"Error: Command timed out after {timeout} seconds.")

        except Exception as e:
            return ToolResult(is_error=True, output=f"Error executing command: {str(e)}")
