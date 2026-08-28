import os
import sys
import asyncio
import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timezone

from app.core.database import run_migrations, engine
from app.core.session_manager import SessionManager, SessionMetadata
from scripts.migrate_sessions_local_to_postgres import migrate_sessions

@pytest.fixture(autouse=True)
def setup_postgres_redis_mode(monkeypatch, tmp_path):
    # Enable postgres_redis mode
    monkeypatch.setenv("COGNITO_STORAGE_BACKEND", "postgres_redis")
    # Mock Redis client using fakeredis for true distributed lock testing
    import fakeredis
    fake_redis = fakeredis.FakeRedis(decode_responses=True)
    fake_async_redis = fakeredis.FakeAsyncRedis(decode_responses=True)
    async def fake_get_async_redis():
        return fake_async_redis
    monkeypatch.setattr("app.core.redis_lock.get_redis_client", lambda: fake_redis)
    monkeypatch.setattr("app.core.redis_lock.get_async_redis_client", fake_get_async_redis)

    # Run DB migrations for testing
    asyncio.run(run_migrations())

@pytest.mark.asyncio
async def test_postgres_redis_shared_session_concurrency(monkeypatch, tmp_path):
    """
    Simulates two backend replicas (Replica A and Replica B) concurrently
    appending messages to the same session in postgres_redis mode.
    Confirms no update loss or message corruption.
    """
    monkeypatch.setenv("COGNITO_STORAGE_BACKEND", "postgres_redis")

    # Instance simulating Replica 1
    replica_a = SessionManager(sessions_dir=tmp_path / "replica_a")
    # Instance simulating Replica 2
    replica_b = SessionManager(sessions_dir=tmp_path / "replica_b")

    # Create session on Replica A
    session_id = replica_a.create(cwd=str(tmp_path), org_id="org-acme", user_id="usr-alice")

    # Verify Replica B can open the same session
    meta_b = await replica_b.open_async(session_id)
    assert meta_b.session_id == session_id
    assert meta_b.org_id == "org-acme"
    assert meta_b.user_id == "usr-alice"

    # Define concurrent writing tasks for Replica A and Replica B
    async def worker_a():
        for i in range(10):
            await replica_a.append_message_async(
                session_id=session_id,
                role="user",
                content=f"Message from Replica A #{i}"
            )
            await asyncio.sleep(0.01)

    async def worker_b():
        for i in range(10):
            await replica_b.append_message_async(
                session_id=session_id,
                role="assistant",
                content=f"Message from Replica B #{i}"
            )
            await asyncio.sleep(0.01)

    # Execute concurrent tasks
    await asyncio.gather(worker_a(), worker_b())

    # Read back effective messages from both replicas
    messages_a = await replica_a.get_effective_messages_async(session_id)
    messages_b = await replica_b.get_effective_messages_async(session_id)

    assert len(messages_a) == 20
    assert len(messages_b) == 20

    # Ensure all 10 messages from Replica A and 10 from Replica B exist
    contents_a = [m["content"] for m in messages_a if "Replica A" in m.get("content", "")]
    contents_b = [m["content"] for m in messages_a if "Replica B" in m.get("content", "")]

    assert len(contents_a) == 10
    assert len(contents_b) == 10

    # Check updated metadata
    meta_updated = await replica_a.open_async(session_id)
    assert meta_updated.message_count == 20

@pytest.mark.asyncio
async def test_postgres_redis_steering_concurrency(monkeypatch, tmp_path):
    """
    Tests concurrent steering message delivery between two replicas.
    """
    monkeypatch.setenv("COGNITO_STORAGE_BACKEND", "postgres_redis")

    replica_a = SessionManager(sessions_dir=tmp_path / "replica_a")
    replica_b = SessionManager(sessions_dir=tmp_path / "replica_b")

    session_id = replica_a.create(cwd=str(tmp_path))

    # Replica A appends a steering message
    steer_id = await replica_a.append_steering_message_async(session_id, "Pause execution")

    # Replica B checks undelivered steering messages
    undelivered_b = await replica_b.get_undelivered_steering_messages_async(session_id)
    assert len(undelivered_b) == 1
    assert undelivered_b[0]["id"] == steer_id
    assert undelivered_b[0]["content"] == "Pause execution"

    # Replica B marks steering message as delivered
    marked = await replica_b.mark_steering_delivered_async(session_id, steering_id=steer_id)
    assert marked is True

    # Replica A checks undelivered steering messages and confirms empty
    undelivered_a = await replica_a.get_undelivered_steering_messages_async(session_id)
    assert len(undelivered_a) == 0

@pytest.mark.asyncio
async def test_local_to_postgres_migration_script(monkeypatch, tmp_path):
    """
    Tests migration script transferring local JSONL & metadata session files to PostgreSQL.
    """
    # 1. Create a local session using local backend mode
    monkeypatch.setenv("COGNITO_STORAGE_BACKEND", "local")
    local_dir = tmp_path / "local_sessions"
    local_mgr = SessionManager(sessions_dir=local_dir)

    sess_id = local_mgr.create(cwd=str(tmp_path), org_id="org-legacy", user_id="usr-legacy")
    local_mgr.append_message(sess_id, "user", "Legacy question 1")
    local_mgr.append_message(sess_id, "assistant", "Legacy answer 1")
    local_mgr.append_compaction(sess_id, "Summary of legacy conversation", 1)
    local_mgr.append_message(sess_id, "user", "Legacy question 2")

    # 2. Run migration script
    result = migrate_sessions(sessions_dir=local_dir)
    assert result["sessions_migrated"] >= 1
    assert result["messages_migrated"] >= 4

    # 3. Switch to postgres_redis mode and verify history
    monkeypatch.setenv("COGNITO_STORAGE_BACKEND", "postgres_redis")
    pg_mgr = SessionManager(sessions_dir=tmp_path / "pg_sessions")

    meta = await pg_mgr.open_async(sess_id)
    assert meta.session_id == sess_id
    assert meta.cwd == str(tmp_path.resolve())

    messages = await pg_mgr.get_effective_messages_async(sess_id)
    assert len(messages) >= 2  # Compaction summary + question 2
