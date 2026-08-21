import json
import logging
import uuid
from typing import AsyncIterator, Dict, List, Optional, Any

from app.core.events import (
    AgentEvent, TextDeltaEvent, ToolCallEvent, ToolResultEvent, DoneEvent, ErrorEvent
)
from app.core.tools.base import AgentTool, ToolContext, ToolResult
from app.core.uncertainty import compute_uncertainty
from app.core.token_budget import apply_token_budget_reminder, estimate_messages_tokens

logger = logging.getLogger(__name__)

async def agent_loop(
    messages: List[Dict[str, Any]],
    tools: List[AgentTool],
    context: ToolContext,
    backend_router,
    model_params: Optional[Dict[str, Any]] = None,
    max_turns: int = 10,
    steering_queue: Optional[Any] = None,
    history_lock: Optional[Any] = None,
    session_manager: Optional[Any] = None,
    session_id: Optional[str] = None,
) -> AsyncIterator[AgentEvent]:
    """
    Main Agent Loop:
    1. Call backend with tools.
    2. Stream text deltas.
    3. Handle tool calls: execute tool, emit ToolResultEvent, add to messages.
    4. Check steering queue before calling LLM or executing tools.
    5. Repeat until end_turn or max_turns.
    """

    current_messages = list(messages)

    async def process_steering():
        if steering_queue is None:
            return
        while not steering_queue.empty():
            try:
                steering_msg = steering_queue.get_nowait()
            except Exception:
                break
            steering_content = f"[STEERING INPUT] {steering_msg}"
            steering_user_msg = {"role": "user", "content": steering_content}
            if history_lock:
                async with history_lock:
                    current_messages.append(steering_user_msg)
                    if session_manager and session_id:
                        session_manager.append_message(session_id, role="user", content=steering_content)
            else:
                current_messages.append(steering_user_msg)
                if session_manager and session_id:
                    session_manager.append_message(session_id, role="user", content=steering_content)
            logger.info(f"Injected steering message into session {session_id}: {steering_content}")
    # Convert AgentTool list to JSON Schema format for the backend
    tools_schema = [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters_schema,
            }
        }
        for t in tools
    ]

    turn = 0
    model_name = (model_params or {}).get("model", "")

    while turn < max_turns:
        turn += 1
        await process_steering()
        # Calculate prompt tokens and apply token budget reminder if tokens exceed 80% of model limit
        current_messages = apply_token_budget_reminder(current_messages, model=model_name)
        total_tokens = estimate_messages_tokens(current_messages, model=model_name)
        logger.info(f"Starting agent turn {turn}/{max_turns} | prompt_tokens={total_tokens} | model={model_name or 'default'}")

        assistant_content = ""
        tool_calls_to_exec = []

        try:
            async for chunk in backend_router.generate_with_tools(current_messages, tools_schema, model_params):
                # Text delta
                if chunk.get("token"):
                    token = chunk["token"]
                    assistant_content += token
                    uncertainty = compute_uncertainty(chunk.get("logprobs"))
                    yield TextDeltaEvent(content=token, uncertainty=uncertainty)

                # Tool calls (Ollama style: array in one chunk; OpenAI style: might be fragmented)
                # For Phase 1 we assume they arrive complete enough to parse
                if chunk.get("tool_calls"):
                    for tc in chunk["tool_calls"]:
                        # Normalize format between Ollama and OpenAI
                        # Ollama: {'function': {'name': ..., 'arguments': {...}}}
                        # OpenAI: {'id': ..., 'type': 'function', 'function': {...}}

                        tc_id = tc.get("id") or f"call_{uuid.uuid4().hex[:8]}"
                        fn = tc.get("function", {})
                        name = fn.get("name")
                        args = fn.get("arguments")

                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except:
                                pass

                        tool_calls_to_exec.append({
                            "id": tc_id,
                            "name": name,
                            "arguments": args
                        })

                        yield ToolCallEvent(
                            tool_call_id=tc_id,
                            tool_name=name,
                            arguments=args if isinstance(args, dict) else {"raw": args}
                        )

            # Add assistant message to history
            # If there were tool calls, we need to add the assistant message with tool_calls
            assistant_message = {"role": "assistant", "content": assistant_content}
            if tool_calls_to_exec:
                # OpenAI format expects tool_calls here
                assistant_message["tool_calls"] = [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {"name": tc["name"], "arguments": json.dumps(tc["arguments"])}
                    }
                    for tc in tool_calls_to_exec
                ]
            current_messages.append(assistant_message)

            if not tool_calls_to_exec:
                # No more tools requested, we are done
                yield DoneEvent(stop_reason="end_turn")
                return

            # Execute tools
            for tc in tool_calls_to_exec:
                await process_steering()
                tool = next((t for t in tools if t.name == tc["name"]), None)
                if not tool:
                    result = ToolResult(is_error=True, output=f"Tool '{tc['name']}' not found.")
                else:
                    logger.info(f"Executing tool {tool.name} with args {tc['arguments']}")
                    result = await tool.execute(tc["arguments"], context)

                yield ToolResultEvent(
                    tool_call_id=tc["id"],
                    tool_name=tc["name"],
                    output=result.output,
                    is_error=result.is_error
                )

                # Add tool result to history
                current_messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "name": tc["name"],
                    "content": result.output
                })

        except Exception as e:
            logger.error(f"Error in agent loop turn {turn}: {e}", exc_info=True)
            yield ErrorEvent(message=str(e))
            yield DoneEvent(stop_reason="error", error_message=str(e))
            return

    yield DoneEvent(stop_reason="max_turns")
