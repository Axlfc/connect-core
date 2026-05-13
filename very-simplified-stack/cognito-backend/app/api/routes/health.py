"""
health.py  (updated)

Health endpoint now reports the status of every backend node individually.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, Optional

from app.services.backend_router import backend_router

router = APIRouter()


class HealthStatus(BaseModel):
    status: str
    version: Optional[str] = None
    backends: Dict[str, str] = {}   # {backend_name: "ok" | "error"}


@router.get("/health", response_model=HealthStatus)
async def health_check():
    """
    Checks the reachability of every registered backend concurrently.
    The top-level status is "ok" when at least one backend is reachable.
    """
    backends = await backend_router.health_all()
    any_ok = any(v == "ok" for v in backends.values())

    return HealthStatus(
        status="ok" if any_ok else "degraded",
        backends=backends,
    )
