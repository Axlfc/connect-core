"""
backend_router.py

GPU-first cascading failover router.

On every request it tries backends in priority order (lowest number first).
If a backend raises any exception it logs the error, marks it as the last
to fail, and immediately tries the next one.  If all backends fail the
original exception from the highest-priority backend is re-raised.

Usage (singleton already exported at the bottom):

    from app.services.backend_router import backend_router

    result = await backend_router.generate(prompt="Hello!")
    # result = {"response": "...", "model": "...", "backend": "...", "attempt": N}
"""

import asyncio
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

from app.services.backend_client import BackendClient
from app.services.backend_registry import BACKENDS_BY_PRIORITY, BackendConfig

logger = logging.getLogger(__name__)


class BackendRouter:
    """
    Manages a pool of BackendClient instances and routes requests
    through them in priority order with automatic failover.
    """

    def __init__(self, configs: list[BackendConfig]):
        self._clients: list[BackendClient] = [BackendClient(c) for c in configs]
        logger.info(
            "BackendRouter initialised with %d backends: %s",
            len(self._clients),
            [c.config.name for c in self._clients],
        )

    def register_backend(self, config: Any):
        """Register a new backend client dynamically."""
        self._clients.append(BackendClient(config))
        logger.info("Backend '%s' registered dynamically via extension.", config.name)

    # ── Public interface ───────────────────────────────────────────────────────

    async def generate(
        self,
        prompt: str,
        model_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Try each backend in priority order.  Returns on first success.
        Raises the last exception if every backend fails.
        """
        last_exc: Optional[Exception] = None

        for attempt, client in enumerate(self._clients, start=1):
            try:
                logger.info(
                    "Attempt %d/%d → backend '%s'",
                    attempt, len(self._clients), client.config.name,
                )
                result = await client.generate(prompt, model_params)
                result["attempt"] = attempt          # traceability in metadata
                logger.info("Success on attempt %d (%s)", attempt, client.config.name)
                return result

            except Exception as exc:
                logger.warning(
                    "Backend '%s' failed (attempt %d): %s",
                    client.config.name, attempt, exc,
                )
                last_exc = exc
                # Continue to next backend

        # All backends exhausted
        logger.error("All %d backends failed.", len(self._clients))
        raise RuntimeError(
            f"All {len(self._clients)} backends failed. "
            f"Last error: {last_exc}"
        ) from last_exc

    async def generate_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        model_params: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Try each backend in priority order for tool-enabled chat.
        If a backend doesn't support tools, it's skipped.
        """
        last_exc: Optional[Exception] = None

        from app.core.retry import retry_transient_stream

        for attempt, client in enumerate(self._clients, start=1):
            try:
                logger.info(
                    "[Tools] Attempt %d/%d → backend '%s'",
                    attempt, len(self._clients), client.config.name,
                )

                async def _stream_raw(target_client=client):
                    async for chunk in target_client.generate_with_tools(messages, tools, model_params):
                        yield chunk

                async for chunk in retry_transient_stream(_stream_raw):
                    yield chunk
                return # Success!

            except (NotImplementedError, RuntimeError) as exc:
                # Handle NotImplementedError (explicitly marked unsupported)
                # or general errors that we might want to failover from
                logger.warning(
                    "[Tools] Backend '%s' skipped (attempt %d): %s",
                    client.config.name, attempt, exc,
                )
                last_exc = exc
                continue
            except Exception as exc:
                logger.warning(
                    "[Tools] Backend '%s' failed (attempt %d): %s",
                    client.config.name, attempt, exc,
                )
                last_exc = exc
                continue

        # All backends exhausted
        logger.error("[Tools] All %d backends failed or unsupported.", len(self._clients))
        raise RuntimeError(
            f"All backends failed or do not support tool calling. "
            f"Last error: {last_exc}"
        )

    async def health_all(self) -> Dict[str, str]:
        """
        Concurrently health-checks every backend.
        Returns {backend_name: "ok" | "error"}.
        """
        async def _check(client: BackendClient) -> tuple[str, str]:
            healthy = await client.check_health()
            return client.config.name, "ok" if healthy else "error"

        results = await asyncio.gather(*[_check(c) for c in self._clients])
        return dict(results)


# ── Singleton ──────────────────────────────────────────────────────────────────
backend_router = BackendRouter(configs=BACKENDS_BY_PRIORITY)
