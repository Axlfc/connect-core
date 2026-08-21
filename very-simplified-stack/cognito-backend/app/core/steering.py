import asyncio
import logging
from typing import Dict

logger = logging.getLogger(__name__)

class SteeringManager:
    """
    Manages per-session asyncio.Queue and asyncio.Lock instances
    for agent steering input.
    """
    def __init__(self):
        self._queues: Dict[str, asyncio.Queue] = {}
        self._locks: Dict[str, asyncio.Lock] = {}

    def get_queue(self, session_id: str) -> asyncio.Queue:
        if session_id not in self._queues:
            self._queues[session_id] = asyncio.Queue()
        return self._queues[session_id]

    def get_lock(self, session_id: str) -> asyncio.Lock:
        if session_id not in self._locks:
            self._locks[session_id] = asyncio.Lock()
        return self._locks[session_id]

    async def post_steering_message(self, session_id: str, message: str) -> None:
        queue = self.get_queue(session_id)
        await queue.put(message)
        logger.info(f"Steering message enqueued for session {session_id}")

    def clear_session(self, session_id: str) -> None:
        self._queues.pop(session_id, None)
        self._locks.pop(session_id, None)

steering_manager = SteeringManager()
