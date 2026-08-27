import json
import asyncio
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from app.core.session_manager import SessionManager
from app.core.session.purger import SessionPurgerTask


@pytest.mark.asyncio
async def test_purge_inactive_sessions_by_age(tmp_path):
    sess_dir = tmp_path / "sessions"
    sess_dir.mkdir()
    mgr = SessionManager(sessions_dir=sess_dir)

    # 1. Create a recent active session (updated now)
    recent_id = mgr.create(cwd=str(tmp_path))

    # 2. Create an old inactive session (updated 35 days ago)
    old_id = mgr.create(cwd=str(tmp_path))
    old_meta_path = sess_dir / f"{old_id}.meta.json"
    with open(old_meta_path, "r") as f:
        meta_data = json.load(f)

    old_time = (datetime.now(timezone.utc) - timedelta(days=35)).isoformat()
    meta_data["updated_at"] = old_time
    meta_data["created_at"] = old_time
    with open(old_meta_path, "w") as f:
        json.dump(meta_data, f)

    # Re-sync index
    mgr._get_index()

    # Verify both sessions exist before purging
    all_before = mgr.list_all()
    all_sids_before = [s.session_id for s in all_before]
    assert recent_id in all_sids_before
    assert old_id in all_sids_before

    # Execute purging for max_age_days = 30
    purged = mgr.purge_inactive_sessions(max_age_days=30)

    assert purged == [old_id]

    # Verify old session files are deleted
    assert not (sess_dir / f"{old_id}.jsonl").exists()
    assert not (sess_dir / f"{old_id}.meta.json").exists()

    # Verify recent session remains intact
    assert (sess_dir / f"{recent_id}.jsonl").exists()
    assert (sess_dir / f"{recent_id}.meta.json").exists()

    all_after = mgr.list_all()
    all_sids_after = [s.session_id for s in all_after]
    assert recent_id in all_sids_after
    assert old_id not in all_sids_after


@pytest.mark.asyncio
async def test_session_purger_background_task(tmp_path, monkeypatch):
    sess_dir = tmp_path / "sessions"
    sess_dir.mkdir()
    mgr = SessionManager(sessions_dir=sess_dir)

    old_id = mgr.create(cwd=str(tmp_path))
    old_meta_path = sess_dir / f"{old_id}.meta.json"
    with open(old_meta_path, "r") as f:
        meta_data = json.load(f)

    old_time = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    meta_data["updated_at"] = old_time
    meta_data["created_at"] = old_time
    with open(old_meta_path, "w") as f:
        json.dump(meta_data, f)

    mgr._get_index()

    purger = SessionPurgerTask(
        session_manager=mgr,
        retention_days=7,
        interval_seconds=1
    )

    purger.start()
    # Wait for purger loop execution
    await asyncio.sleep(0.3)
    await purger.stop()

    all_after = mgr.list_all()
    all_sids_after = [s.session_id for s in all_after]
    assert old_id not in all_sids_after
