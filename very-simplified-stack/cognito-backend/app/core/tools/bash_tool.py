import asyncio
import os
import re
from typing import Any, Dict
from app.core.tools.base import AgentTool, ToolContext, ToolResult

class BashTool(AgentTool):
    name = "bash"
    description = "Execute a bash command in the current workspace."
    parameters_schema = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "The bash command to execute."},
            "timeout_seconds": {"type": "integer", "description": "Command timeout in seconds.", "default": 30},
        },
        "required": ["command"],
    }

    async def execute(self, arguments: Dict[str, Any], context: ToolContext) -> ToolResult:
        command = arguments.get("command")
        timeout = min(int(arguments.get("timeout_seconds", 30)), 120)

        if not command:
            return ToolResult(is_error=True, output="Error: command is required.")

        # sudo rejection
        if re.search(r"\bsudo\b", command, re.IGNORECASE):
            return ToolResult(is_error=True, output="Error: Use of 'sudo' is strictly forbidden.")

        # Trust check
        if not context.trusted:
            return ToolResult(is_error=True, output="Proyecto no confiado (untrusted). Ejecuta project-trust set antes de ejecutar comandos.")

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
