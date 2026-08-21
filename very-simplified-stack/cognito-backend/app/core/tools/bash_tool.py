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

        # Rejection for sudo
        if re.search(r"\bsudo\b", command, re.IGNORECASE):
            return ToolResult(is_error=True, output="Error: Use of 'sudo' is strictly forbidden.")

        # Check session approval cache first (Auto-approval reuse)
        is_cache_approved = self.approval_cache.is_approved(session_id, command)

        if user_approved:
            # Store in cache upon user explicit approval
            self.approval_cache.approve(session_id, command)

        auto_approved = is_cache_approved or user_approved

        if not auto_approved:
            # Evaluate execution policy
            requires_approval = self.exec_policy.requires_explicit_approval(
                command, project_trusted=context.trusted
            )

            if requires_approval:
                return ToolResult(
                    is_error=True,
                    output=(
                        f"Command requires explicit user approval due to ExecPolicy or untrusted project context. "
                        f"Command: '{command}'. Pass user_approved=True or approve in current session."
                    )
                )

        try:
            # Run the command with a timeout
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=context.cwd
            )

            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
                output = (stdout + stderr).decode("utf-8")
                return ToolResult(output=output)
            except asyncio.TimeoutError:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
                return ToolResult(is_error=True, output=f"Error: Command timed out after {timeout} seconds.")

        except Exception as e:
            return ToolResult(is_error=True, output=f"Error executing command: {str(e)}")
