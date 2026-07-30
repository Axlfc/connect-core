import os
from typing import Any, Dict
from app.core.tools.base import AgentTool, ToolContext, ToolResult

class ShellTools(AgentTool):
    """
    Persistent Bash session runner (NOOA-15).
    """
    name = "shell_run"
    description = "Executes shell commands inside a persistent bash session."
    parameters_schema = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "The command to run."}
        },
        "required": ["command"]
    }

    async def execute(self, arguments: dict[str, Any], context: ToolContext) -> ToolResult:
        import subprocess
        cmd = arguments.get("command", "")
        try:
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=context.cwd, timeout=30)
            output = f"STDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}\nEXIT CODE: {res.returncode}"
            return ToolResult(output=output, is_error=res.returncode != 0)
        except Exception as e:
            return ToolResult(output=str(e), is_error=True)

class TodoTools(AgentTool):
    """
    Simple todo manager tool.
    """
    name = "todo_manage"
    description = "Add or view elements in your TODO list."
    parameters_schema = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["add", "list"], "description": "Action to perform"},
            "item": {"type": "string", "description": "Task to add"}
        },
        "required": ["action"]
    }

    _todo_list = []

    async def execute(self, arguments: dict[str, Any], context: ToolContext) -> ToolResult:
        action = arguments.get("action")
        item = arguments.get("item")

        if action == "add" and item:
            self._todo_list.append(item)
            return ToolResult(output=f"Added item: {item}")
        else:
            return ToolResult(output=f"TODO List:\n" + "\n".join(f"- {i}" for i in self._todo_list))

class WebPublisherTools(AgentTool):
    name = "web_publish"
    description = "Exports a simple HTML report to local static server path."
    parameters_schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "content_html": {"type": "string"}
        },
        "required": ["title", "content_html"]
    }

    async def execute(self, arguments: dict[str, Any], context: ToolContext) -> ToolResult:
        title = arguments.get("title")
        content = arguments.get("content_html")
        filepath = os.path.join(context.cwd, "report.html") if hasattr(context, "cwd") else "report.html"
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"<html><head><title>{title}</title></head><body>{content}</body></html>")
            return ToolResult(output=f"Report successfully published to {filepath}")
        except Exception as e:
            return ToolResult(output=str(e), is_error=True)
