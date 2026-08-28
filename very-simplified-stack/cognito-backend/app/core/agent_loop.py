import asyncio
import json
import logging
import re
import uuid
from typing import AsyncIterator, Dict, List, Optional, Any

from app.core.events import (
    AgentEvent, TextDeltaEvent, ToolCallEvent, ToolResultEvent, DoneEvent, ErrorEvent, ApprovalRequiredEvent
)
from app.core.tools.base import AgentTool, ToolContext, ToolResult
from app.core.tools.remember_fact_tool import RememberFactTool
from app.core.uncertainty import compute_uncertainty
from app.core.token_budget import apply_token_budget_reminder, estimate_messages_tokens
from app.core.guardrails.tool_loop_detector import ToolLoopDetector
from app.core.exec_policy import evaluate_command_execution, evaluate_tool_execution, ExecVerdict
from app.core.approval import approval_manager, ApprovalManager
from app.core.extensions.registry import extension_registry
from app.core.extensions.api import AgentStartPayload, ToolPreExecPayload, ToolPostExecPayload
from app.core.logging_config import get_trace_id

logger = logging.getLogger(__name__)

def sanitize_tool_output(output: str) -> str:
    """
    Sanitizes raw tool output to prevent prompt injection / context escaping.
    Legacy helper retained for backwards compatibility with tests and callers.
    """
    if not isinstance(output, str):
        return output
    replacements = [
        (re.compile(r'</tool_output\s*>', re.IGNORECASE), r'<\/tool_output>'),
        (re.compile(r'<tool_output(\s|>)', re.IGNORECASE), r'<\\tool_output\1'),
        (re.compile(r'</system\s*>', re.IGNORECASE), r'<\/system>'),
        (re.compile(r'<system(\s|>)', re.IGNORECASE), r'<\\system\1'),
    ]
    sanitized = output
    for pattern, repl in replacements:
        sanitized = pattern.sub(repl, sanitized)
    return sanitized

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
    steering_manager: Optional[Any] = None,
    approval_timeout_seconds: Optional[int] = None,
    planning_phase: bool = True,
    read_only_turns: int = 1,
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
        sm_mgr = steering_manager
        if sm_mgr is None:
            from app.core.steering import steering_manager as default_sm
            sm_mgr = default_sm
        if session_manager and session_id:
            await sm_mgr.sync_pending_steering_async(session_id, session_manager)

        while not steering_queue.empty():
            try:
                steering_msg = steering_queue.get_nowait()
            except Exception:
                break
            steering_id = getattr(steering_msg, "id", None)
            msg_content = str(steering_msg)
            steering_content = f"[STEERING INPUT] {msg_content}"
            steering_user_msg = {"role": "user", "content": steering_content}
            if history_lock:
                async with history_lock:
                    current_messages.append(steering_user_msg)
                    if session_manager and session_id:
                        session_manager.append_message(session_id, role="user", content=steering_content)
                        session_manager.mark_steering_delivered(
                            session_id, steering_id=steering_id, content=msg_content
                        )
            else:
                current_messages.append(steering_user_msg)
                if session_manager and session_id:
                    session_manager.append_message(session_id, role="user", content=steering_content)
                    session_manager.mark_steering_delivered(
                        session_id, steering_id=steering_id, content=msg_content
                    )
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
    tool_loop_detector = ToolLoopDetector(window_size=4, threshold=3)
    eff_session_id = session_id or getattr(context, "session_id", None) or "default_session"

    await extension_registry.fire(
        "on_agent_start",
        AgentStartPayload(
            session_id=eff_session_id,
            cwd=context.cwd,
            messages=current_messages,
            model_name=model_name,
            max_turns=max_turns,
            trace_id=get_trace_id()
        ),
        cwd=context.cwd
    )

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

            # Partition tool calls into contiguous batches based on concurrency_safe metadata and execution policy
            batches: List[tuple[str, List[tuple[dict, Optional[AgentTool]]]]] = []
            current_batch: List[tuple[dict, Optional[AgentTool]]] = []

            for tc in tool_calls_to_exec:
                tool = next((t for t in tools if t.name == tc["name"]), None)
                cmd = tc["arguments"].get("command", "") if isinstance(tc.get("arguments"), dict) else ""
                user_approved = bool(tc["arguments"].get("user_approved", False)) if isinstance(tc.get("arguments"), dict) else False
                eff_session_id = session_id or getattr(context, "session_id", None) or "default_session"

                is_safe_parallel = False
                if tool and getattr(tool, "concurrency_safe", False):
                    verdict, _ = evaluate_tool_execution(
                        tool=tool,
                        arguments=tc["arguments"] if isinstance(tc.get("arguments"), dict) else {},
                        command=cmd,
                        cwd=context.cwd,
                        trusted=context.trusted,
                        session_id=eff_session_id,
                        user_approved=user_approved,
                        turn=turn,
                        planning_phase=planning_phase,
                        read_only_turns=read_only_turns,
                    )
                    if verdict == ExecVerdict.PERMITIR:
                        is_safe_parallel = True

                if is_safe_parallel:
                    current_batch.append((tc, tool))
                else:
                    if current_batch:
                        batches.append(("parallel", current_batch))
                        current_batch = []
                    batches.append(("sequential", [(tc, tool)]))
            if current_batch:
                batches.append(("parallel", current_batch))

            # Execute tool batches
            for batch_mode, batch_items in batches:
                await process_steering()

                if batch_mode == "parallel" and len(batch_items) > 1:
                    logger.info(f"Executing {len(batch_items)} tool calls in parallel using concurrency_safe metadata")

                    async def _exec_single_parallel(tc_item: dict, tool_obj: Optional[AgentTool]) -> ToolResult:
                        p_args = tc_item["arguments"] if isinstance(tc_item.get("arguments"), dict) else {"raw": tc_item.get("arguments")}
                        p_id = tc_item.get("id", "")
                        p_name = tc_item.get("name", "")

                        veto = await extension_registry.fire(
                            "on_tool_pre_exec",
                            ToolPreExecPayload(
                                session_id=eff_session_id,
                                cwd=context.cwd,
                                tool_name=p_name,
                                arguments=p_args,
                                tool_call_id=p_id,
                                turn=turn,
                                trace_id=get_trace_id()
                            ),
                            cwd=context.cwd
                        )

                        if veto:
                            res = ToolResult(is_error=True, output=f"Acción bloqueada por hook de seguridad (on_tool_pre_exec): {veto}")
                        else:
                            try:
                                if isinstance(tool_obj, AgentTool):
                                    res = await tool_obj.validate_and_execute(p_args, context)
                                else:
                                    res = await tool_obj.execute(p_args, context)
                            except Exception as ex:
                                res = ToolResult(is_error=True, output=f"Error executing parallel tool '{p_name}': {ex}")

                        await extension_registry.fire(
                            "on_tool_post_exec",
                            ToolPostExecPayload(
                                session_id=eff_session_id,
                                cwd=context.cwd,
                                tool_name=p_name,
                                arguments=p_args,
                                tool_call_id=p_id,
                                output=res.output,
                                is_error=res.is_error,
                                turn=turn,
                                trace_id=get_trace_id()
                            ),
                            cwd=context.cwd
                        )
                        return res

                    exec_tasks = [_exec_single_parallel(tc_item, tool_obj) for tc_item, tool_obj in batch_items]
                    results = await asyncio.gather(*exec_tasks)

                    for (tc, tool), result in zip(batch_items, results):
                        turn_nonce = uuid.uuid4().hex[:12]
                        sanitized_output = sanitize_tool_output(result.output)
                        formatted_output = f'<tool_output_{turn_nonce} source="{tc["name"]}">\n{sanitized_output}\n</tool_output_{turn_nonce}>'

                        yield ToolResultEvent(
                            tool_call_id=tc["id"],
                            tool_name=tc["name"],
                            output=formatted_output,
                            is_error=result.is_error
                        )

                        current_messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "name": tc["name"],
                            "content": formatted_output
                        })

                        warning_msg = tool_loop_detector.record_and_check(
                            tc["name"], tc["arguments"], output=result.output, tool=tool
                        )
                        if warning_msg:
                            logger.warning(f"Tool loop detected for '{tc['name']}'. Injecting system warning message.")
                            system_warning_msg = {"role": "system", "content": warning_msg}
                            current_messages.append(system_warning_msg)
                            if session_manager and session_id:
                                if history_lock:
                                    async with history_lock:
                                        session_manager.append_message(session_id, role="system", content=warning_msg)
                                else:
                                    session_manager.append_message(session_id, role="system", content=warning_msg)
                else:
                    # Sequential execution path (single tool call or unsafe tool call)
                    for tc, tool in batch_items:
                        tc_args = tc["arguments"] if isinstance(tc.get("arguments"), dict) else {"raw": tc.get("arguments")}
                        tc_id = tc.get("id", "")
                        tc_name = tc.get("name", "")

                        veto = await extension_registry.fire(
                            "on_tool_pre_exec",
                            ToolPreExecPayload(
                                session_id=eff_session_id,
                                cwd=context.cwd,
                                tool_name=tc_name,
                                arguments=tc_args,
                                tool_call_id=tc_id,
                                turn=turn,
                                trace_id=get_trace_id()
                            ),
                            cwd=context.cwd
                        )

                        if veto:
                            logger.warning(f"Tool execution for '{tc_name}' blocked by on_tool_pre_exec hook: {veto}")
                            result = ToolResult(is_error=True, output=f"Acción bloqueada por hook de seguridad (on_tool_pre_exec): {veto}")
                        elif not tool:
                            result = ToolResult(is_error=True, output=f"Tool '{tc_name}' not found.")
                        else:
                            logger.info(f"Preparing execution for tool {tool.name} with args {tc['arguments']}")

                            cmd = tc["arguments"].get("command", "") if isinstance(tc.get("arguments"), dict) else ""
                            user_approved = bool(tc["arguments"].get("user_approved", False)) if isinstance(tc.get("arguments"), dict) else False

                            verdict, reason = evaluate_tool_execution(
                                tool=tool,
                                arguments=tc["arguments"] if isinstance(tc.get("arguments"), dict) else {},
                                command=cmd,
                                cwd=context.cwd,
                                trusted=context.trusted,
                                session_id=eff_session_id,
                                user_approved=user_approved,
                                turn=turn,
                                planning_phase=planning_phase,
                                read_only_turns=read_only_turns,
                            )

                            if verdict == ExecVerdict.DENEGAR:
                                logger.warning(f"Tool execution for '{tc['name']}' denied by ExecPolicy: {reason}")
                                result = ToolResult(is_error=True, output=f"Error: {reason}")
                            elif verdict == ExecVerdict.REQUIERE_APROBACION:
                                logger.info(f"Tool execution for '{tc['name']}' requires approval: {reason}")
                                eff_timeout = approval_manager.get_effective_timeout(
                                    session_id=eff_session_id,
                                    request_timeout=approval_timeout_seconds
                                )
                                appr_req = await approval_manager.create_request(
                                    session_id=eff_session_id,
                                    tool_name=tc["name"],
                                    arguments=tc["arguments"] if isinstance(tc["arguments"], dict) else {"raw": tc["arguments"]},
                                    reason=reason,
                                    command=cmd,
                                    timeout_seconds=eff_timeout,
                                    is_destructive=getattr(tool, "is_destructive", False),
                                    is_read_only=getattr(tool, "is_read_only", False),
                                )
                                appr_id = appr_req.approval_id

                                req_event = ApprovalRequiredEvent(
                                    approval_id=appr_id,
                                    session_id=eff_session_id,
                                    tool_name=tc["name"],
                                    arguments=tc["arguments"] if isinstance(tc["arguments"], dict) else {"raw": tc["arguments"]},
                                    reason=reason,
                                    timeout_seconds=appr_req.timeout_seconds,
                                )
                                yield req_event

                                if session_manager and eff_session_id:
                                    steer_notice = (
                                        f"[SOLICITUD DE APROBACIÓN {appr_id}] Acción sensible requerida: '{cmd or tc['name']}'. "
                                        f"Razón: {reason}. Timeout: {appr_req.timeout_seconds}s."
                                    )
                                    try:
                                        if history_lock:
                                            async with history_lock:
                                                await session_manager.append_steering_message_async(eff_session_id, steer_notice, steering_id=appr_id)
                                        else:
                                            await session_manager.append_steering_message_async(eff_session_id, steer_notice, steering_id=appr_id)
                                    except Exception as ex:
                                        logger.debug(f"Failed to append approval notification to steering log: {ex}")

                                decision = await approval_manager.wait_for_decision(appr_id)

                                if decision.status == "approved":
                                    logger.info(f"Approval [{decision.approval_id}] granted by {decision.actor}. Executing tool.")
                                    if isinstance(tc.get("arguments"), dict):
                                        tc["arguments"]["user_approved"] = True
                                    if isinstance(tool, AgentTool):
                                        result = await tool.validate_and_execute(tc["arguments"], context)
                                    else:
                                        result = await tool.execute(tc["arguments"], context)
                                else:
                                    logger.warning(f"Approval [{decision.approval_id}] status: {decision.status} ({decision.reason}). Skipping execution.")
                                    if session_manager and eff_session_id:
                                        block_notice = (
                                            f"[ACCION_BLOQUEADA_POR_APROBACION_HUMANA] La acción '{cmd or tc['name']}' "
                                            f"fue bloqueada ({decision.status}). Razón: {decision.reason}"
                                        )
                                        try:
                                            if history_lock:
                                                async with history_lock:
                                                    await session_manager.append_steering_message_async(
                                                        eff_session_id, block_notice, steering_id=f"blocked-{appr_id}"
                                                    )
                                                    await session_manager.record_blocked_approval_async(
                                                        eff_session_id, decision.model_dump()
                                                    )
                                            else:
                                                await session_manager.append_steering_message_async(
                                                    eff_session_id, block_notice, steering_id=f"blocked-{appr_id}"
                                                )
                                                await session_manager.record_blocked_approval_async(
                                                    eff_session_id, decision.model_dump()
                                                )
                                        except Exception as ex:
                                            logger.debug(f"Failed to record block notification in session manager: {ex}")

                                    result = ToolResult(
                                        is_error=True,
                                        output=f"Acción denegada por política de aprobación humana ({decision.status}): {decision.reason}"
                                    )
                            else:
                                if isinstance(tool, AgentTool):
                                    result = await tool.validate_and_execute(tc["arguments"], context)
                                else:
                                    result = await tool.execute(tc["arguments"], context)

                        await extension_registry.fire(
                            "on_tool_post_exec",
                            ToolPostExecPayload(
                                session_id=eff_session_id,
                                cwd=context.cwd,
                                tool_name=tc_name,
                                arguments=tc_args,
                                tool_call_id=tc_id,
                                output=result.output,
                                is_error=result.is_error,
                                turn=turn,
                                trace_id=get_trace_id()
                            ),
                            cwd=context.cwd
                        )

                        turn_nonce = uuid.uuid4().hex[:12]
                        sanitized_output = sanitize_tool_output(result.output)
                        formatted_output = f'<tool_output_{turn_nonce} source="{tc["name"]}">\n{sanitized_output}\n</tool_output_{turn_nonce}>'

                        yield ToolResultEvent(
                            tool_call_id=tc["id"],
                            tool_name=tc["name"],
                            output=formatted_output,
                            is_error=result.is_error
                        )

                        current_messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "name": tc["name"],
                            "content": formatted_output
                        })

                        warning_msg = tool_loop_detector.record_and_check(
                            tc["name"], tc["arguments"], output=result.output, tool=tool
                        )
                        if warning_msg:
                            logger.warning(f"Tool loop detected for '{tc['name']}'. Injecting system warning message.")
                            system_warning_msg = {"role": "system", "content": warning_msg}
                            current_messages.append(system_warning_msg)
                            if session_manager and session_id:
                                if history_lock:
                                    async with history_lock:
                                        session_manager.append_message(session_id, role="system", content=warning_msg)
                                else:
                                    session_manager.append_message(session_id, role="system", content=warning_msg)

        except Exception as e:
            logger.error(f"Error in agent loop turn {turn}: {e}", exc_info=True)
            err_msg = f"No se pudo completar tras reintentos: {e}"
            yield ErrorEvent(message=err_msg)
            yield DoneEvent(stop_reason="error", error_message=err_msg)
            return

    yield DoneEvent(stop_reason="max_turns")
