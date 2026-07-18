import os
import asyncio
import json
import logging
import uuid
import time
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.models.db import DBOutboxEvent
from app.core.database import async_session_factory

logger = logging.getLogger("cognito.backend.outbox")

# Simple Redis mock/wrapper in case redis-py is not installed or service is down
try:
    import redis
    redis_available = True
except ImportError:
    redis_available = False

class OutboxPublisher:
    def __init__(self):
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        redis_password = os.getenv("REDIS_PASSWORD", "")

        self.redis_url = f"redis://:{redis_password}@{redis_host}:{redis_port}/0"
        self._r_client = None

    def _get_client(self):
        global redis_available
        if not redis_available:
            return None
        if self._r_client is None:
            try:
                import os
                self._r_client = redis.Redis.from_url(self.redis_url, socket_timeout=2.0)
                self._r_client.ping()
            except Exception as e:
                logger.warning(f"Redis is temporarily unavailable: {e}")
                self._r_client = None
        return self._r_client

    async def publish_to_redis(self, task_id: str, event: dict) -> bool:
        """
        Publishes the event to Redis under the namespace 'cognito:events:<task_id>'.
        """
        client = self._get_client()
        if not client:
            return False
        try:
            channel = f"cognito:events:{task_id}"
            client.publish(channel, json.dumps(event))
            return True
        except Exception as e:
            logger.warning(f"Failed to publish event to Redis: {e}")
            self._r_client = None # Reset client for reconnect
            return False

    async def save_and_publish_event(self, session: AsyncSession, aggregate_type: str, aggregate_id: str, event_type: str, payload: dict) -> str:
        """
        Implements Transactional Outbox.
        Inserts event into DBOutboxEvent first, and publishes to Redis after commit.
        """
        event_id = f"evt-{uuid.uuid4().hex[:12]}"
        db_evt = DBOutboxEvent(
            event_id=event_id,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_type=event_type,
            payload=payload,
            is_delivered=False,
            timestamp=time.time()
        )
        session.add(db_evt)
        # Flush so it has committed state, but don't commit yet (session ownership has transaction control)
        await session.flush()

        # We schedule Redis publishing after the session's transaction commits.
        # To make it super robust, we can publish immediately if session committed,
        # or have a background task. Let's write an async call to do so.
        async def publish_after_commit():
            # Wait a tiny fraction to allow commit to complete
            await asyncio.sleep(0.05)
            async with async_session_factory() as fresh_sess:
                pub_ok = await self.publish_to_redis(aggregate_id, {
                    "event_id": event_id,
                    "event_type": event_type,
                    "payload": payload
                })
                if pub_ok:
                    await fresh_sess.execute(
                        update(DBOutboxEvent)
                        .where(DBOutboxEvent.event_id == event_id)
                        .values(is_delivered=True)
                    )
                    await fresh_sess.commit()

        # Fire and forget publishing
        asyncio.create_task(publish_after_commit())
        return event_id

    async def replay_undelivered_events(self):
        """
        Background/startup replayer to send any failed/undelivered outbox events to Redis.
        """
        async with async_session_factory() as session:
            res = await session.execute(
                select(DBOutboxEvent).where(DBOutboxEvent.is_delivered == False).limit(100)
            )
            undelivered = res.scalars().all()
            if not undelivered:
                return

            logger.info(f"Replaying {len(undelivered)} undelivered outbox events to Redis...")
            for evt in undelivered:
                pub_ok = await self.publish_to_redis(evt.aggregate_id, {
                    "event_id": evt.event_id,
                    "event_type": evt.event_type,
                    "payload": evt.payload
                })
                if pub_ok:
                    evt.is_delivered = True
            await session.commit()

outbox_publisher = OutboxPublisher()
