from fastapi import APIRouter
from app.models.ai import HealthStatus
from app.services.ollama_client import ollama_client

router = APIRouter()

@router.get("/health", response_model=HealthStatus)
async def health_check():
    """
    Enhanced health check endpoint that verifies the service's own status
    and the status of its dependency (Ollama service).
    """
    ollama_status = await ollama_client.check_health()
    return HealthStatus(
        status="ok",
        ollama_status=ollama_status
    )
