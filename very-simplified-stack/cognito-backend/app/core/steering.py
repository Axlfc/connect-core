import asyncio
import logging
from typing import Dict

logger = logging.getLogger(__name__)

from typing import Dict, Set, Optional, Any

class SteeringString(str):
    id: Optional[str]

class SteeringManager:
    """
    Manages per-session asyncio.Queue and asyncio.Lock instances
    for agent steering input, integrated with durable session persistence.
    """
    def __init__(self):
        self._queues: Dict[str, asyncio.Queue] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._enqueued_ids: Dict[str, Set[str]] = {}

    def get_queue(self, session_id: str) -> asyncio.Queue:
        if session_id not in self._queues:
            self._queues[session_id] = asyncio.Queue()
        return self._queues[session_id]

    def get_lock(self, session_id: str) -> asyncio.Lock:
        if session_id not in self._locks:
            self._locks[session_id] = asyncio.Lock()
        return self._locks[session_id]

    async def post_steering_message(
        self, session_id: str, message: str, session_manager: Optional[Any] = None
    ) -> str:
        if session_manager is None:
            from app.core.session_manager import SessionManager
            session_manager = SessionManager()

        steering_id = await session_manager.append_steering_message_async(session_id, message)

        msg_obj = SteeringString(message)
        msg_obj.id = steering_id

        queue = self.get_queue(session_id)
        await queue.put(msg_obj)
        self._enqueued_ids.setdefault(session_id, set()).add(steering_id)

        logger.info(f"Steering message {steering_id} enqueued and persisted for session {session_id}")
        return steering_id

    def sync_pending_steering(self, session_id: str, session_manager: Any) -> None:
        undelivered = session_manager.get_undelivered_steering_messages(session_id)
        if not undelivered:
            return

        queue = self.get_queue(session_id)
        enqueued_set = self._enqueued_ids.setdefault(session_id, set())

        for item in undelivered:
            sid = item.get("id")
            content = item.get("content")
            if sid and sid not in enqueued_set:
                msg_obj = SteeringString(content)
                msg_obj.id = sid
                queue.put_nowait(msg_obj)
                enqueued_set.add(sid)
                logger.info(f"Re-enqueued undelivered steering message {sid} for session {session_id}")

    async def sync_pending_steering_async(self, session_id: str, session_manager: Any) -> None:
        import anyio
        await anyio.to_thread.run_sync(self.sync_pending_steering, session_id, session_manager)

    def clear_session(self, session_id: str) -> None:
        self._queues.pop(session_id, None)
        self._locks.pop(session_id, None)
        self._enqueued_ids.pop(session_id, None)

steering_manager = SteeringManager()
