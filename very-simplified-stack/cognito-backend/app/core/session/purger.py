import os
import asyncio
import logging
from typing import Optional
from app.core.session_manager import SessionManager

logger = logging.getLogger("cognito.backend.session_purger")

class SessionPurgerTask:
    """
    Background task using standard asyncio to periodically purge inactive sessions.
    Configurable via environment variables:
    - COGNITO_SESSION_RETENTION_DAYS: Retention window in days (default: 30)
    - COGNITO_SESSION_PURGE_INTERVAL_SECONDS: Run interval in seconds (default: 3600)
    """
    def __init__(
        self,
        session_manager: Optional[SessionManager] = None,
        retention_days: Optional[int] = None,
        interval_seconds: Optional[int] = None,
    ):
        self.session_manager = session_manager or SessionManager()

        env_retention = os.getenv("COGNITO_SESSION_RETENTION_DAYS", "30").strip()
        try:
            self.retention_days = retention_days if retention_days is not None else int(env_retention)
        except ValueError:
            self.retention_days = 30

        env_interval = os.getenv("COGNITO_SESSION_PURGE_INTERVAL_SECONDS", "3600").strip()
        try:
            self.interval_seconds = interval_seconds if interval_seconds is not None else int(env_interval)
        except ValueError:
            self.interval_seconds = 3600

        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def _loop(self):
        logger.info(
            f"Started background session purger task | "
            f"retention_days={self.retention_days} | interval_seconds={self.interval_seconds}"
        )
        while self._running:
            try:
                purged = await self.session_manager.purge_inactive_sessions_async(
                    max_age_days=self.retention_days
                )
                if purged:
                    logger.info(f"Background purger cleaned up {len(purged)} inactive session(s): {purged}")
            except Exception as e:
                logger.error(f"Error during background session purge cycle: {e}", exc_info=True)

            try:
                await asyncio.sleep(self.interval_seconds)
            except asyncio.CancelledError:
                break

    def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self):
        if not self._running:
            return
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Background session purger task stopped.")
