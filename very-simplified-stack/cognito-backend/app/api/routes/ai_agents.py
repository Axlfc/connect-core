from fastapi import APIRouter, HTTPException
from app.models.ai import AIRequest, AIResponse
from app.services.reasoning_engine import reasoning_engine
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

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
