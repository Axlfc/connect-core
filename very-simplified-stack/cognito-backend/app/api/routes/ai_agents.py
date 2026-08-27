import json
import time
import anyio
from collections import deque
from typing import List, Optional, Any, Dict
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.models.ai import AIRequest, AIResponse
from app.services.reasoning_engine import reasoning_engine
from app.services.backend_router import backend_router
from app.services.semantic_orchestrator import semantic_orchestrator
from app.core.agent_loop import agent_loop
from app.core.tools.base import ToolContext
from app.core.tools.read_tool import ReadTool
from app.core.tools.write_tool import WriteTool
from app.core.tools.edit_tool import EditTool
from app.core.tools.bash_tool import BashTool
from app.core.project_trust import ProjectTrustStore
from app.core.resource_loader import ResourceLoader
from app.core.session_manager import SessionManager
from app.core.compaction import should_compact, compact
from app.core.token_budget import apply_token_budget_reminder, estimate_messages_tokens
from app.core.events import SessionInfoEvent, TextDeltaEvent, ToolCallEvent, ToolResultEvent, DoneEvent, ErrorEvent
from app.core.session.message_deriver import derive_messages_for_llm, DerivationConfig
from app.core.extensions.registry import extension_registry
from app.core.steering import steering_manager
from app.core.approval import approval_manager, PendingApprovalRequest, ApprovalDecisionAudit
import logging

from typing import Literal
from app.models.domain import Task, TaskContext, RouteDecision, ApprovalRequest, ExecutionAttempt, VerificationRun, EscalationDecision, ModelDescriptor
from app.services.ollama_classifier import ollama_task_classifier
from app.services.policy_engine import policy_engine
from app.services.task_store import task_store
from app.services.escalation_service import escalation_service
from app.services.model_discovery import model_discovery_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

class AgentLoopRequest(BaseModel):
    messages: List[Dict[str, Any]]
    cwd: str
    session_id: Optional[str] = None
    model_params: Optional[Dict[str, Any]] = None
    approval_timeout_seconds: Optional[int] = None
    planning_phase: Optional[bool] = True
    read_only_turns: int = 1

class SteerRequest(BaseModel):
    message: str

class HumanApprovalDecisionRequest(BaseModel):
    decision: Literal["approved", "denied"]
    actor: str = "operator"
    reason: Optional[str] = None

class SecretReloadRequest(BaseModel):
    name: Optional[str] = None
    auth_token: Optional[str] = None
    token: Optional[str] = None

class SecretReloadResponse(BaseModel):
    status: str
    message: str
    invalidated_secret: Optional[str] = None


class SlidingWindowRateLimiter:
    """
    Sliding window rate limiter protecting sensitive administrative endpoints against DoS.
    """
    def __init__(self, max_requests: int = 5, window_seconds: float = 60.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._timestamps: deque = deque()

    def check(self) -> bool:
        now = time.time()
        while self._timestamps and (now - self._timestamps[0]) > self.window_seconds:
            self._timestamps.popleft()

        if len(self._timestamps) >= self.max_requests:
            return False

        self._timestamps.append(now)
        return True

    def reset(self) -> None:
        self._timestamps.clear()


secrets_reload_rate_limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=60.0)


def _extract_and_verify_admin_auth(
    request: Request,
    req: Optional[SecretReloadRequest] = None,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
) -> None:
    """
    Extracts administrative authentication token from HTTP headers or request body,
    and verifies it against SecretsProvider via verify_mcp_auth.
    Raises 401 Unauthorized if verification fails.
    """
    token: Optional[str] = None

    if authorization:
        if authorization.lower().startswith("bearer "):
            token = authorization[7:].strip()
        else:
            token = authorization.strip()

    if not token and x_api_key:
        token = x_api_key.strip()

    if not token:
        auth_hdr = request.headers.get("Authorization") or request.headers.get("authorization")
        if auth_hdr:
            if auth_hdr.lower().startswith("bearer "):
                token = auth_hdr[7:].strip()
            else:
                token = auth_hdr.strip()
        if not token:
            api_key_hdr = request.headers.get("X-API-Key") or request.headers.get("x-api-key")
            if api_key_hdr:
                token = api_key_hdr.strip()

    if not token and req:
        token = req.auth_token or req.token

    from app.services.mcp_server import verify_mcp_auth
    if not token or not verify_mcp_auth(token):
        logger.warning("Unauthenticated or invalid token access attempt to administrative endpoint.")
        raise HTTPException(
            status_code=401,
            detail="Authentication failed. Invalid or missing authorization token."
        )

@router.post("/agent", response_model=AIResponse)
async def run_ai_agent(request: AIRequest):
    """
    Endpoint to process an AI request.

    This endpoint receives a prompt, sends it to the reasoning engine,
    and returns the AI-generated response along with performance metrics.
    """
    logger.info(f"Received request for AI agent with session ID: {request.session_id or 'N/A'}")
    try:
        response = await reasoning_engine.process_request(request)
        return response
    except Exception as e:
        logger.error(f"Failed to process AI request: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while processing the AI request."
        )

@router.post("/agent/loop")
async def run_agent_loop(request: AgentLoopRequest):
    """
    Agent Loop endpoint (SSE) with Session Management.
    """
    logger.info(f"Starting agent loop in {request.cwd} | session_id={request.session_id}")

    session_manager = SessionManager()
    is_new = False
    session_id = request.session_id

    # 1. Resolver session_id
    try:
        if session_id == "latest":
            session_id = session_manager.continue_recent(request.cwd)
            if not session_id:
                session_id = session_manager.create(request.cwd, approval_timeout_seconds=request.approval_timeout_seconds)
                is_new = True
        elif session_id:
            metadata = session_manager.open(session_id)
            if metadata.cwd != str(Path(request.cwd).resolve()):
                error_msg = f"CWD mismatch: session {session_id} is for {metadata.cwd}, request is for {request.cwd}"
                logger.error(error_msg)
                return StreamingResponse(
                    iter([f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"]),
                    media_type="text/event-stream"
                )
        else:
            session_id = session_manager.create(request.cwd, approval_timeout_seconds=request.approval_timeout_seconds)
            is_new = True

        if request.approval_timeout_seconds is not None:
            approval_manager.set_session_timeout(session_id, request.approval_timeout_seconds)
            await session_manager.set_approval_timeout_async(session_id, request.approval_timeout_seconds)
    except Exception as e:
        logger.error(f"Session resolution failed: {e}")
        return StreamingResponse(
            iter([f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"]),
            media_type="text/event-stream"
        )

    # 2. Cargar historial y compactar si es necesario (offloaded to thread to avoid blocking event loop on flock)
    effective_messages = await session_manager.get_effective_messages_async(session_id)
    if await should_compact(effective_messages):
        try:
            last_line = await anyio.to_thread.run_sync(session_manager.get_last_line_index, session_id)
            summary, context_ledger = await compact(effective_messages, backend_router=backend_router)
            await anyio.to_thread.run_sync(session_manager.append_compaction, session_id, summary, last_line, context_ledger)
        except Exception as e:
            logger.warning(f"Compaction failed for session {session_id}, continuing anyway: {e}")

    # 3. Preparar contexto y herramientas
    loader = ResourceLoader(request.cwd)
    trust_store = ProjectTrustStore()
    context = ToolContext(
        cwd=request.cwd,
        trusted=trust_store.is_trusted(request.cwd),
        protected_files=loader.get_effective_protected_files()
    )
    # Refresh local extensions for the project before fetching tools
    extension_registry.refresh("project_local", request.cwd, backend_router, semantic_orchestrator)
    tools = extension_registry.tools_for(request.cwd)

    new_messages = list(request.messages)
    model_name = (request.model_params or {}).get("model", "")

    # Derivar el array completo de mensajes usando el patron Event Log vs. Derived Messages
    derivation_config = DerivationConfig(
        cwd=request.cwd,
        model_name=model_name,
        sessions_dir=session_manager.sessions_dir,
        extra_messages=new_messages
    )
    full_messages_for_loop = await derive_messages_for_llm(session_id, config=derivation_config)
    total_tokens = estimate_messages_tokens(full_messages_for_loop, model=model_name)
    logger.info(f"Agent loop prompt token budget estimate: {total_tokens} tokens for model '{model_name or 'default'}'")

    await steering_manager.sync_pending_steering_async(session_id, session_manager)
    steering_queue = steering_manager.get_queue(session_id)
    history_lock = steering_manager.get_lock(session_id)

    # Checkpointing note (AUD-026): Storage operations are performed against SessionManager.
    # PENDING REVIEW: Re-evaluate once RFC Phase 6 database storage migration lands.
    async def event_generator_v2():
        # Persist incoming new messages from request only if not already present in session history (AUD-026 resumption)
        existing_history = await session_manager.get_effective_messages_async(session_id)
        async with history_lock:
            for msg in new_messages:
                already_exists = any(
                    h.get("role") == msg.get("role") and h.get("content") == msg.get("content")
                    for h in existing_history
                )
                if not already_exists:
                    await session_manager.append_message_async(session_id, msg["role"], msg["content"])

        yield f"data: {SessionInfoEvent(session_id=session_id, is_new=is_new).model_dump_json()}\n\n"

        assistant_content = ""
        current_tool_calls = []

        try:
            try:
                loop_iter = agent_loop(
                    messages=full_messages_for_loop,
                    tools=tools,
                    context=context,
                    backend_router=backend_router,
                    model_params=request.model_params,
                    steering_queue=steering_queue,
                    history_lock=history_lock,
                    session_manager=session_manager,
                    session_id=session_id,
                    steering_manager=steering_manager,
                    approval_timeout_seconds=request.approval_timeout_seconds,
                    planning_phase=request.planning_phase if request.planning_phase is not None else True,
                    read_only_turns=request.read_only_turns,
                )
            except TypeError:
                loop_iter = agent_loop(
                    messages=full_messages_for_loop,
                    tools=tools,
                    context=context,
                    backend_router=backend_router,
                    model_params=request.model_params,
                    planning_phase=request.planning_phase if request.planning_phase is not None else True,
                    read_only_turns=request.read_only_turns,
                )
            async for event in loop_iter:
                if isinstance(event, TextDeltaEvent):
                    assistant_content += event.content
                elif isinstance(event, ToolCallEvent):
                    current_tool_calls.append({
                        "id": event.tool_call_id,
                        "type": "function",
                        "function": {"name": event.tool_name, "arguments": json.dumps(event.arguments)}
                    })
                elif isinstance(event, ToolResultEvent):
                    # Checkpoint assistant message and tool result immediately after turn (AUD-026)
                    async with history_lock:
                        if assistant_content or current_tool_calls:
                            await session_manager.append_message_async(
                                session_id,
                                role="assistant",
                                content=assistant_content,
                                tool_calls=current_tool_calls if current_tool_calls else None
                            )
                            assistant_content = ""
                            current_tool_calls = []

                        await session_manager.append_message_async(
                            session_id,
                            role="tool",
                            content=event.output,
                            tool_name=event.tool_name,
                            tool_call_id=event.tool_call_id
                        )
                elif isinstance(event, DoneEvent):
                    async with history_lock:
                        if assistant_content or current_tool_calls:
                            await session_manager.append_message_async(
                                session_id,
                                role="assistant",
                                content=assistant_content,
                                tool_calls=current_tool_calls if current_tool_calls else None
                            )

                yield f"data: {event.model_dump_json()}\n\n"
        except Exception as e:
            logger.error(f"Error in agent loop generator: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator_v2(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )

@router.get("/agent/sessions")
async def list_sessions(cwd: Optional[str] = None):
    """
    List all sessions, optionally filtered by cwd.
    """
    session_manager = SessionManager()
    return session_manager.list_all(cwd=cwd)

@router.get("/agent/sessions/{session_id}")
async def get_session(session_id: str):
    """
    Get session metadata and effective messages.
    """
    session_manager = SessionManager()
    try:
        metadata = await session_manager.open_async(session_id)
        messages = await session_manager.get_effective_messages_async(session_id)
        return {
            "metadata": metadata,
            "messages": messages
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

@router.post("/agent/sessions/{session_id}/fork")
async def fork_session(session_id: str):
    """
    Fork an existing session into a new one.
    """
    session_manager = SessionManager()
    try:
        new_id = session_manager.fork_from(session_id)
        return {"session_id": new_id}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

@router.post("/agent/sessions/{session_id}/steer")
async def steer_session(session_id: str, request: SteerRequest):
    """
    Enqueue a steering message for an active agent loop session.
    """
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="Steering message cannot be empty")

    session_manager = SessionManager()
    try:
        session_manager.open(session_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    await steering_manager.post_steering_message(session_id, request.message, session_manager=session_manager)
    return {
        "status": "success",
        "session_id": session_id,
        "message": request.message
    }

@router.get("/agent/approvals/pending", response_model=List[PendingApprovalRequest])
async def list_pending_approvals(session_id: Optional[str] = None):
    """
    List currently active pending human approval requests for sensitive agent actions.
    """
    return await approval_manager.list_pending(session_id=session_id)

@router.get("/agent/approvals/audit-logs", response_model=List[ApprovalDecisionAudit])
async def list_approval_audit_logs(session_id: Optional[str] = None):
    """
    Retrieve structured audit decision logs for human-in-the-loop approvals.
    """
    return await approval_manager.get_audit_logs(session_id=session_id)

@router.post("/agent/approvals/{approval_id}/decide", response_model=ApprovalDecisionAudit)
async def submit_approval_decision(approval_id: str, req: HumanApprovalDecisionRequest):
    """
    Submit human decision (approved or denied) for a pending sensitive action request.
    """
    is_approved = (req.decision == "approved")
    audit_record = await approval_manager.submit_decision(
        approval_id=approval_id,
        approved=is_approved,
        actor=req.actor,
        reason=req.reason
    )
    if not audit_record:
        raise HTTPException(status_code=404, detail=f"Pending approval request '{approval_id}' not found or already resolved.")
    return audit_record

@router.post("/secrets/reload", response_model=SecretReloadResponse)
async def reload_secrets(
    request: Request,
    req: Optional[SecretReloadRequest] = None,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
):
    """
    Triggers dynamic invalidation and reloading of secrets (e.g. AuthToken, APIKey)
    without restarting the backend process.
    Requires administrative authentication (Bearer token / X-API-Key / body auth_token)
    and enforces rate limiting (max 5 calls per minute).
    """
    # 1. Rate Limiting Check
    if not secrets_reload_rate_limiter.check():
        logger.warning("Rate limit exceeded for /api/secrets/reload endpoint.")
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded for secrets reload. Maximum 5 requests per minute allowed."
        )

    # 2. Authentication Check
    _extract_and_verify_admin_auth(request=request, req=req, authorization=authorization, x_api_key=x_api_key)

    # 3. Dynamic secret invalidation
    from app.core.secrets import get_secrets_provider
    provider = get_secrets_provider()
    secret_name = req.name if req else None
    provider.invalidate(secret_name)
    target_str = f"'{secret_name}'" if secret_name else "all secrets"
    logger.info(f"Secrets provider invalidated {target_str} via API endpoint.")
    return SecretReloadResponse(
        status="success",
        message=f"Successfully invalidated {target_str}.",
        invalidated_secret=secret_name
    )


# ══════════════════════════════════════════════════════════════════════════════
# Cognito-Codex Intelligent Router endpoints
# ══════════════════════════════════════════════════════════════════════════════

class PreviewRouteRequest(BaseModel):
    user_task: str
    workspace_folder: str
    active_file: Optional[str] = None
    selected_language: Optional[str] = None
    selected_text_size: Optional[int] = None
    diagnostics_summary: Optional[Dict[str, Any]] = None
    git_status_summary: Optional[str] = None
    changed_files_count: int = 0
    detected_technologies: List[str] = []

class CreateTaskRequest(BaseModel):
    task_id: Optional[str] = None
    session_id: str
    title: str
    requirements: str
    context: TaskContext

class ApproveRequest(BaseModel):
    approval_id: str
    status: Literal["approved", "denied"]
    reason: Optional[str] = None

@router.get("/agent/models/catalog")
async def get_combined_catalog():
    """
    Combined models catalog API.
    """
    catalog = await model_discovery_service.get_combined_catalog()
    return {"catalog": catalog}

@router.post("/agent/route/preview", response_model=RouteDecision)
async def preview_route(req: PreviewRouteRequest):
    """
    Evaluates a task context and outputs a RouteDecision preview.
    """
    from app.models.domain import RepositoryContext, EditorContext, TaskContext
    import uuid

    repo = RepositoryContext(
        repository_id="preview-repo",
        root_path=req.workspace_folder,
        current_branch="main",
        base_commit="HEAD",
        is_dirty=False,
        changed_files_count=req.changed_files_count,
        detected_technologies=req.detected_technologies
    )
    editor = EditorContext(
        workspace_folder=req.workspace_folder,
        active_file=req.active_file,
        selected_language=req.selected_language,
        selected_text_size=req.selected_text_size,
        diagnostics_summary=req.diagnostics_summary,
        git_status_summary=req.git_status_summary
    )
    context = TaskContext(
        repository=repo,
        editor=editor,
        user_task=req.user_task
    )

    classification = await ollama_task_classifier.classify_task(context)
    decision = policy_engine.evaluate(context, classification)
    return decision

@router.post("/agent/tasks", response_model=Task)
async def create_task(req: CreateTaskRequest):
    """
    Idempotent task creation.
    """
    import uuid
    task_id = req.task_id or f"task-{uuid.uuid4().hex[:12]}"

    # 1. Preview/Calculate decision
    classification = await ollama_task_classifier.classify_task(req.context)
    decision = policy_engine.evaluate(req.context, classification)

    task = Task(
        task_id=task_id,
        session_id=req.session_id,
        title=req.title,
        requirements=req.requirements,
        context=req.context,
        route_decision=decision,
        status="pending"
    )
    await task_store.create_task(task)
    return task

@router.get("/agent/tasks", response_model=List[Task])
async def list_tasks(session_id: Optional[str] = None):
    return await task_store.list_tasks(session_id=session_id)

@router.get("/agent/tasks/{task_id}", response_model=Task)
async def get_task(task_id: str):
    task = await task_store.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@router.post("/agent/tasks/{task_id}/approve")
async def approve_task_request(task_id: str, req: ApproveRequest):
    appr = await task_store.update_approval(req.approval_id, req.status, req.reason)
    if not appr:
        raise HTTPException(status_code=404, detail="Approval request not found")
    return appr

@router.post("/agent/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    task = await task_store.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await task_store.update_task_status(task_id, "cancelled")
    return {"status": "success", "message": f"Task {task_id} marked as cancelled"}

@router.post("/agent/tasks/{task_id}/retry")
async def retry_task(task_id: str):
    task = await task_store.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Simple manual retry/escalation trigger
    attempts = await task_store.get_attempts(task_id)
    attempt_num = len(attempts) + 1

    # If escalated, get next logical tier
    decision = task.route_decision
    if attempts:
        last_attempt = attempts[-1]
        next_tier = escalation_service.escalation_chain.get(last_attempt.route_decision.logical_tier)
        if next_tier:
            decision = last_attempt.route_decision.model_copy()
            decision.logical_tier = next_tier
            decision.resolved_model_identifier = f"codex.{next_tier}" if next_tier != "sol" else "codex.max"

    attempt = await escalation_service.execute_task_attempt(task, attempt_num, decision)
    return {"status": "success", "attempt": attempt}
