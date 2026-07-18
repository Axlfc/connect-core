import os
os.environ["COGNITO_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

import pytest
import json
import logging
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import Base, engine, async_session_factory, check_schema_health, run_migrations
from app.models.db import DBTask, DBOutboxEvent
from app.services.outbox import outbox_publisher
from app.services.qdrant_memory import qdrant_memory
from app.services.mcp_server import mcp_server
from app.core.logging_config import StructuredJSONFormatter, correlation_context, set_correlation_ids

@pytest.mark.asyncio
async def test_database_schema_and_migrations():
    # Run migrations against local SQLite or mock engine
    await run_migrations()
    assert await check_schema_health() is True

@pytest.mark.asyncio
async def test_transactional_outbox_pattern():
    await run_migrations()
    async with async_session_factory() as session:
        # Save outbox event in transaction
        evt_id = await outbox_publisher.save_and_publish_event(
            session, "task", "task-outbox-1", "task_created", {"some": "data"}
        )
        await session.commit()

        # Verify event exists in DB
        res = await session.execute(
            select(DBOutboxEvent).where(DBOutboxEvent.event_id == evt_id)
        )
        evt = res.scalar_one()
        assert evt is not None
        assert evt.aggregate_id == "task-outbox-1"
        assert evt.event_type == "task_created"

    # Wait a fraction for background publisher
    await asyncio.sleep(0.1)

    # Replay undelivered events (should also work and clean up)
    await outbox_publisher.replay_undelivered_events()

@pytest.mark.asyncio
async def test_qdrant_outage_fallback():
    # If QdrantClient is down or host is fake, index_point must fail gracefully (return False instead of crashing)
    res = await qdrant_memory.index_point(
        "cognito_repository_context", "pt-123", [0.1]*128, {"repository_id": "r1"}
    )
    assert res is False # Graceful failure / offline fallback

@pytest.mark.asyncio
async def test_mcp_recursion_prevention():
    # Depth within limit
    assert mcp_server.validate_recursion("codex", "corr-1", 2) is True

    # Depth exceeding limit (blocked)
    assert mcp_server.validate_recursion("codex", "corr-1", 4) is False

    # Calling tool beyond depth returns error JSON
    res = await mcp_server.call_tool(
        "cognito_architecture_context", {}, "codex", "corr-1", execution_depth=5
    )
    assert res["is_error"] is True
    assert "Recursive execution depth limit exceeded" in res["output"]

def test_structured_json_logging():
    # Set correlation ids
    set_correlation_ids(task_id="t-99", correlation_id="c-99")

    formatter = StructuredJSONFormatter()
    log_record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Structured logging check",
        args=(),
        exc_info=None
    )

    formatted = formatter.format(log_record)
    data = json.loads(formatted)

    assert data["message"] == "Structured logging check"
    assert data["task_id"] == "t-99"
    assert data["correlation_id"] == "c-99"

    correlation_context.set({}) # Reset
