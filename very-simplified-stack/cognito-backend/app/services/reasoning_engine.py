"""
reasoning_engine.py  (updated)

Orchestrates AI requests through the BackendRouter (GPU-first cascading failover).
Drop-in replacement for the original — the public interface is identical.
"""

import time
import logging
from app.services.backend_router import backend_router, BackendRouter
from app.models.ai import AIRequest, AIResponse

logger = logging.getLogger(__name__)


class ReasoningEngine:
    """
    Thin orchestration layer: times the request, delegates to the router,
    and wraps the result in an AIResponse.
    """

    def __init__(self, router: BackendRouter):
        self.router = router

    async def process_request(self, request: AIRequest) -> AIResponse:
        start = time.perf_counter()
        logger.info("Processing request | session=%s", request.session_id or "N/A")

        model_params = request.parameters or None

        try:
            result = await self.router.generate(
                prompt=request.prompt,
                model_params=model_params,
            )
        except Exception:
            logger.error("All backends failed for request", exc_info=True)
            raise

        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "Request done in %.2f ms | backend=%s | attempt=%s",
            duration_ms, result.get("backend"), result.get("attempt"),
        )

        return AIResponse(
            text=result["response"],  # <--- CAMBIA 'response=' POR 'text='
            session_id=request.session_id,
            metadata={
                "duration_ms": duration_ms,
                "model_used": result.get("model"),
                "backend": result.get("backend"),
                "attempt": result.get("attempt"),
            },
        )


# Singleton — uses the shared router singleton
reasoning_engine = ReasoningEngine(router=backend_router)
