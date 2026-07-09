import json
from typing import List, Optional, Any, Dict
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
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

class AgentLoopRequest(BaseModel):
    messages: List[Dict[str, Any]]
    cwd: str
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
    Agent Loop endpoint (SSE).
    """
    logger.info(f"Starting agent loop in {request.cwd}")

    loader = ResourceLoader(request.cwd)
    trust_store = ProjectTrustStore()

    context = ToolContext(
        cwd=request.cwd,
        trusted=trust_store.is_trusted(request.cwd),
        protected_files=loader.get_effective_protected_files()
    )

    tools = [ReadTool(), WriteTool(), EditTool(), BashTool()]

    # Inyectar AGENTS.md en el system prompt si existe
    agents_md = loader.discover_agents_md()
    messages = list(request.messages)
    if agents_md:
        system_msg = next((m for m in messages if m["role"] == "system"), None)
        if system_msg:
            system_msg["content"] += f"\n\nContext from AGENTS.md:\n{agents_md}"
        else:
            messages.insert(0, {"role": "system", "content": f"Context from AGENTS.md:\n{agents_md}"})

    async def event_generator():
        try:
            async for event in agent_loop(
                messages=messages,
                tools=tools,
                context=context,
                backend_router=backend_router,
                model_params=request.model_params
            ):
                yield f"data: {event.model_dump_json()}\n\n"
        except Exception as e:
            logger.error(f"Error in agent loop generator: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )
