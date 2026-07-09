import json
from typing import List, Optional, Any, Dict
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.models.ai import AIRequest, AIResponse
from app.services.reasoning_engine import reasoning_engine
from app.services.backend_router import backend_router
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
from app.core.events import SessionInfoEvent, TextDeltaEvent, ToolCallEvent, ToolResultEvent, DoneEvent, ErrorEvent
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

class AgentLoopRequest(BaseModel):
    messages: List[Dict[str, Any]]
    cwd: str
    session_id: Optional[str] = None
    model_params: Optional[Dict[str, Any]] = None

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
                session_id = session_manager.create(request.cwd)
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
            session_id = session_manager.create(request.cwd)
            is_new = True
    except Exception as e:
        logger.error(f"Session resolution failed: {e}")
        return StreamingResponse(
            iter([f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"]),
            media_type="text/event-stream"
        )

    # 2. Cargar historial y compactar si es necesario
    effective_messages = session_manager.get_effective_messages(session_id)
    if await should_compact(effective_messages):
        try:
            last_line = session_manager.get_last_line_index(session_id)
            summary = await compact(effective_messages, backend_router=backend_router)
            session_manager.append_compaction(session_id, summary, last_line)
            effective_messages = session_manager.get_effective_messages(session_id)
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
    tools = [ReadTool(), WriteTool(), EditTool(), BashTool()]

    # Inyectar AGENTS.md
    agents_md = loader.discover_agents_md()
    history = list(effective_messages)
    if agents_md:
        system_msg = next((m for m in history if m["role"] == "system"), None)
        if system_msg:
            system_msg["content"] += f"\n\nContext from AGENTS.md:\n{agents_md}"
        else:
            history.insert(0, {"role": "system", "content": f"Context from AGENTS.md:\n{agents_md}"})

    # Mensajes nuevos de la request
    new_messages = list(request.messages)
    full_messages_for_loop = history + new_messages

    # REDESIGN: To persist assistant messages correctly, we need to capture them.
    # The current agent_loop yields events but doesn't return the full objects.
    async def event_generator_v2():
        # Persist incoming new messages from request
        for msg in new_messages:
            session_manager.append_message(session_id, msg["role"], msg["content"])

        yield f"data: {SessionInfoEvent(session_id=session_id, is_new=is_new).model_dump_json()}\n\n"

        assistant_content = ""
        current_tool_calls = []

        try:
            async for event in agent_loop(
                messages=full_messages_for_loop,
                tools=tools,
                context=context,
                backend_router=backend_router,
                model_params=request.model_params
            ):
                if isinstance(event, TextDeltaEvent):
                    assistant_content += event.content
                elif isinstance(event, ToolCallEvent):
                    current_tool_calls.append({
                        "id": event.tool_call_id,
                        "type": "function",
                        "function": {"name": event.tool_name, "arguments": json.dumps(event.arguments)}
                    })
                elif isinstance(event, ToolResultEvent):
                    # Before persisting tool result, we MUST persist the assistant message that called it
                    if assistant_content or current_tool_calls:
                        session_manager.append_message(
                            session_id,
                            role="assistant",
                            content=assistant_content,
                            tool_calls=current_tool_calls if current_tool_calls else None
                        )
                        assistant_content = ""
                        current_tool_calls = []

                    session_manager.append_message(
                        session_id,
                        role="tool",
                        content=event.output,
                        tool_name=event.tool_name,
                        tool_call_id=event.tool_call_id
                    )
                elif isinstance(event, DoneEvent):
                    if assistant_content or current_tool_calls:
                        session_manager.append_message(
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
        metadata = session_manager.open(session_id)
        messages = session_manager.get_effective_messages(session_id)
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
