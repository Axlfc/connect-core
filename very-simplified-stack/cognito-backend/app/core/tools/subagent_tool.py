import asyncio
import logging
from typing import Any, Dict, List, Optional
from app.core.tools.base import AgentTool, ToolContext, ToolResult
from app.core.events import TextDeltaEvent, ToolResultEvent, DoneEvent

logger = logging.getLogger(__name__)

class SubAgentTool(AgentTool):
    """
    SubAgentTool allows the primary agent to delegate bounded sub-tasks
    (e.g., code inspection, search, localized analysis) to an isolated sub-agent
    running concurrently with explicit time limits and turn limits.
    """
    name = "delegate_subagent"
    description = (
        "Delegates a bounded sub-task (e.g. searching, code inspection, analysis) "
        "to a parallel sub-agent with strict time and scope limits."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "task_description": {
                "type": "string",
                "description": "Clear description of the sub-task for the sub-agent to perform."
            },
            "timeout_seconds": {
                "type": "integer",
                "description": "Maximum execution time in seconds for the sub-agent (default: 30).",
                "default": 30
            },
            "max_turns": {
                "type": "integer",
                "description": "Maximum turns allowed for the sub-agent loop (default: 5).",
                "default": 5
            },
            "allowed_tools": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of tool names the sub-agent is permitted to use."
            }
        },
        "required": ["task_description"]
    }

    is_read_only = True
    is_destructive = False
    concurrency_safe = True

    def __init__(self, backend_router=None, available_tools: Optional[List[AgentTool]] = None):
        self.backend_router = backend_router
        self.available_tools = available_tools or []

    async def execute(self, arguments: dict[str, Any], context: ToolContext) -> ToolResult:
        task_description = arguments.get("task_description")
        if not task_description:
            return ToolResult(is_error=True, output="Error: 'task_description' is required.")

        timeout_seconds = arguments.get("timeout_seconds", 30)
        max_turns = arguments.get("max_turns", 5)
        allowed_tools = arguments.get("allowed_tools")

        # Select tools for sub-agent (filtering read-only / concurrency_safe tools if restricted)
        from app.core.extensions.registry import extension_registry
        candidate_tools = self.available_tools or extension_registry.tools_for(context.cwd)

        # Restrict tools if allowed_tools list specified
        if allowed_tools is not None:
            subagent_tools = [t for t in candidate_tools if t.name in allowed_tools]
        else:
            # By default, sub-agents get safe read-only tools to enforce strict bounding
            subagent_tools = [t for t in candidate_tools if getattr(t, "is_read_only", True) and getattr(t, "name") != self.name]

        from app.services.backend_router import backend_router as default_router
        router = self.backend_router or default_router

        from app.core.agent_loop import agent_loop

        subagent_messages = [
            {
                "role": "system",
                "content": (
                    "You are a specialized sub-agent assigned to complete a bounded task. "
                    "Focus strictly on the requested task and provide a concise, factual summary of your findings. "
                    "Do not make unauthorized modifications outside your sub-task."
                )
            },
            {"role": "user", "content": task_description}
        ]

        logger.info(f"SubAgent started for task: '{task_description[:60]}...' (timeout={timeout_seconds}s, max_turns={max_turns})")

        async def _run_subagent():
            collected_text = []
            tool_results = []
            async for event in agent_loop(
                messages=subagent_messages,
                tools=subagent_tools,
                context=context,
                backend_router=router,
                max_turns=max_turns,
                planning_phase=False,  # Sub-agent operates directly within allocated turns
                read_only_turns=0,
            ):
                if isinstance(event, TextDeltaEvent):
                    collected_text.append(event.content)
                elif isinstance(event, ToolResultEvent):
                    tool_results.append(f"[{event.tool_name}]: {event.output[:200]}")
                elif isinstance(event, DoneEvent):
                    break

            final_text = "".join(collected_text).strip()
            summary = final_text or "\n".join(tool_results) or "Sub-agent completed with no textual output."
            return summary

        try:
            result_summary = await asyncio.wait_for(_run_subagent(), timeout=float(timeout_seconds))
            return ToolResult(
                is_error=False,
                output=f"[SUB-AGENT RESULT]\nTask: {task_description}\nResult:\n{result_summary}"
            )
        except asyncio.TimeoutError:
            logger.warning(f"SubAgent timed out after {timeout_seconds}s for task: '{task_description}'")
            return ToolResult(
                is_error=True,
                output=f"[SUB-AGENT TIMEOUT]\nTask '{task_description}' exceeded the limit of {timeout_seconds}s."
            )
        except Exception as e:
            logger.error(f"SubAgent failed for task '{task_description}': {e}", exc_info=True)
            return ToolResult(
                is_error=True,
                output=f"[SUB-AGENT ERROR]\nTask failed: {e}"
            )
