from fastapi import APIRouter
from typing import List, Dict, Any

router = APIRouter(prefix="/api/dev", tags=["Dev Tooling"])

@router.get("/traces")
async def list_traces() -> List[Dict[str, Any]]:
    """
    Simulated trace provider endpoint for local React Trace Viewer SPA (NOOA-23).
    """
    return [
        {
            "span_id": "span_01",
            "name": "UnifiedLLMCall",
            "type": "llm",
            "inputs": {"prompt": "Hola"},
            "outputs": {"response": "Hola, ¿en qué puedo ayudarte?"}
        }
    ]
