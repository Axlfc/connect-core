import os
import sys
import json
import pytest
import asyncio
import subprocess
import tracemalloc
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.database import get_db_session, get_db_sync_session, Base
from app.models.db import DBJulesSession, DBJulesActivity, DBSource, DBApiKey
from app.core.jules_auth import generate_api_key, hash_api_key
from scripts.import_jules_export import import_jules_export

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "synthetic_jules_export"

class SyncToAsyncSessionAdapter:
    def __init__(self, sync_session: Session):
        self._sync = sync_session

    async def execute(self, statement, *args, **kwargs):
        return self._sync.execute(statement, *args, **kwargs)

    async def commit(self):
        self._sync.commit()

    async def rollback(self):
        self._sync.rollback()

    async def close(self):
        self._sync.close()

async def override_get_db_session():
    sync_sess = get_db_sync_session()
    try:
        yield SyncToAsyncSessionAdapter(sync_sess)
    finally:
        sync_sess.close()

app.dependency_overrides[get_db_session] = override_get_db_session

@pytest.fixture(autouse=True)
def setup_test_db():
    db = get_db_sync_session()
    # Clean tables before each test
    db.query(DBJulesActivity).delete()
    db.query(DBJulesSession).delete()
    db.query(DBSource).delete()
    db.query(DBApiKey).delete()
    db.commit()
    yield db


def test_import_idempotency_and_byte_for_byte_preservation(setup_test_db):
    db = setup_test_db

    # First import
    ret1 = import_jules_export([str(FIXTURE_DIR)], owner="owner_test_1")
    assert ret1 == 0

    session_count_1 = db.query(DBJulesSession).count()
    activity_count_1 = db.query(DBJulesActivity).count()
    assert session_count_1 == 1
    assert activity_count_1 == 5

    # Verify 9 decimal places preserved byte-for-byte
    sess = db.query(DBJulesSession).filter(DBJulesSession.session_id == "10001").first()
    assert sess.create_time == "2025-01-15T10:00:00.123456789Z"
    assert sess.update_time == "2025-01-15T10:05:00.987654321Z"

    act1 = db.query(DBJulesActivity).filter(DBJulesActivity.activity_id == "32a1b2c3d4e5f678901234567890abcdef").first()
    assert act1.create_time == "2025-01-15T10:00:00.123456789Z"

    act2 = db.query(DBJulesActivity).filter(DBJulesActivity.activity_id == "task-10001-activity-step-1").first()
    assert act2.create_time == "2025-01-15T10:01:00.123456789Z"

    # Re-import (idempotency check)
    ret2 = import_jules_export([str(FIXTURE_DIR)], owner="owner_test_1")
    assert ret2 == 0

    session_count_2 = db.query(DBJulesSession).count()
    activity_count_2 = db.query(DBJulesActivity).count()
    assert session_count_2 == 1
    assert activity_count_2 == 5


def test_jules_v1alpha_auth_and_endpoints(setup_test_db):
    db = setup_test_db
    import_jules_export([str(FIXTURE_DIR)], owner="owner_test_1")

    full_key, key_hash, visible_prefix = generate_api_key()
    api_key_obj = DBApiKey(
        key_id="key_101",
        key_hash=key_hash,
        visible_prefix=visible_prefix,
        owner="owner_test_1"
    )
    db.add(api_key_obj)
    db.commit()

    client = TestClient(app)

    # 1. Unauthenticated request -> 401 in Jules error format
    resp_unauth = client.get("/v1alpha/sessions")
    assert resp_unauth.status_code == 401
    assert "error" in resp_unauth.json()
    assert resp_unauth.json()["error"]["status"] == "UNAUTHENTICATED"

    # 2. Authenticated GET /v1alpha/sessions
    headers = {"x-goog-api-key": full_key}
    resp_sess = client.get("/v1alpha/sessions", headers=headers)
    assert resp_sess.status_code == 200
    data_sess = resp_sess.json()
    assert "sessions" in data_sess
    assert len(data_sess["sessions"]) == 1
    assert data_sess["sessions"][0]["id"] == "10001"
    assert data_sess["sessions"][0]["createTime"] == "2025-01-15T10:00:00.123456789Z"

    # 3. Structural comparison for GET /v1alpha/sessions/10001
    resp_sess_detail = client.get("/v1alpha/sessions/10001", headers=headers)
    assert resp_sess_detail.status_code == 200
    with open(FIXTURE_DIR / "sessions" / "10001" / "session.json", "r") as f:
        expected_session = json.load(f)
    assert resp_sess_detail.json() == expected_session

    # 4. Structural comparison for GET /v1alpha/sessions/10001/activities
    resp_act = client.get("/v1alpha/sessions/10001/activities", headers=headers)
    assert resp_act.status_code == 200
    data_act = resp_act.json()
    assert "activities" in data_act
    assert len(data_act["activities"]) == 5
    with open(FIXTURE_DIR / "sessions" / "10001" / "activities.json", "r") as f:
        expected_activities = json.load(f)
    assert data_act["activities"] == expected_activities

    # 5. GET /v1alpha/sources with repository containing dots (hypenosys.github.io)
    resp_sources = client.get("/v1alpha/sources", headers=headers)
    assert resp_sources.status_code == 200
    sources = resp_sources.json()["sources"]
    assert len(sources) == 2
    source_names = [s["name"] for s in sources]
    assert "sources/github/hypenosys/hypenosys.github.io" in source_names

    # GET specific source path with dots
    resp_single_source = client.get("/v1alpha/sources/github/hypenosys/hypenosys.github.io", headers=headers)
    assert resp_single_source.status_code == 200
    assert resp_single_source.json()["githubRepo"]["repo"] == "hypenosys.github.io"


def test_session_id_validation(setup_test_db):
    db = setup_test_db
    full_key, key_hash, visible_prefix = generate_api_key()
    api_key_obj = DBApiKey(
        key_id="key_102",
        key_hash=key_hash,
        visible_prefix=visible_prefix,
        owner="owner_test_1"
    )
    db.add(api_key_obj)
    db.commit()

    client = TestClient(app)
    headers = {"x-goog-api-key": full_key}

    # Session ID with colon (e.g. GET /sessions/123:sendMessage) -> 404 in Jules error format
    resp = client.get("/v1alpha/sessions/123:sendMessage", headers=headers)
    assert resp.status_code == 404
    err = resp.json()["error"]
    assert err["code"] == 404
    assert err["status"] == "NOT_FOUND"


def test_cors_preflight_options(setup_test_db):
    db = setup_test_db
    full_key, key_hash, visible_prefix = generate_api_key()
    api_key_obj = DBApiKey(
        key_id="key_103",
        key_hash=key_hash,
        visible_prefix=visible_prefix,
        owner="owner_test_1"
    )
    db.add(api_key_obj)
    db.commit()

    client = TestClient(app)
    headers = {
        "Origin": "https://dev.hypenosys.com",
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "x-goog-api-key, Content-Type"
    }
    resp_preflight = client.options("/v1alpha/sessions", headers=headers)
    assert resp_preflight.status_code == 200
    assert "x-goog-api-key" in resp_preflight.headers.get("access-control-allow-headers", "").lower()

    # Expose-Headers are sent on actual CORS GET requests
    resp_get = client.get("/v1alpha/sessions", headers={"Origin": "https://dev.hypenosys.com", "x-goog-api-key": full_key})
    assert resp_get.status_code == 200
    assert "retry-after" in resp_get.headers.get("access-control-expose-headers", "").lower()


def test_owner_required_cli(tmp_path):
    script_path = Path(__file__).resolve().parent.parent / "scripts" / "import_jules_export.py"
    cmd = [sys.executable, str(script_path), str(tmp_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode != 0
    assert "required" in result.stderr.lower()
    assert "--owner" in result.stderr.lower()


def test_manifest_completeness_check_and_allow_partial(setup_test_db, tmp_path):
    db = setup_test_db

    # Create 3-part synthetic export in tmp_path
    part1_dir = tmp_path / "part1"
    part2_dir = tmp_path / "part2"

    part1_dir.mkdir()
    part2_dir.mkdir()

    # part1 has manifest & sessions.json listing 3 sessions (sess1, sess2, sess3)
    manifest = {
        "sessions_by_part": {
            "part1": ["sess1"],
            "part2": ["sess2"],
            "part3": ["sess3"]
        }
    }
    with open(part1_dir / "manifest.json", "w") as f:
        json.dump(manifest, f)

    sessions_summary = [
        {"id": "sess1", "createTime": "2025-01-01T00:00:00Z"},
        {"id": "sess2", "createTime": "2025-01-01T00:00:00Z"},
        {"id": "sess3", "createTime": "2025-01-01T00:00:00Z"}
    ]
    with open(part1_dir / "sessions.json", "w") as f:
        json.dump(sessions_summary, f)

    # part1 contains sess1 files
    s1_dir = part1_dir / "sessions" / "sess1"
    s1_dir.mkdir(parents=True)
    with open(s1_dir / "session.json", "w") as f:
        json.dump({"id": "sess1", "state": "COMPLETED"}, f)
    with open(s1_dir / "activities.json", "w") as f:
        json.dump([{"id": "act1", "createTime": "2025-01-01T00:00:00Z"}], f)

    # part2 contains sess2 files
    s2_dir = part2_dir / "sessions" / "sess2"
    s2_dir.mkdir(parents=True)
    with open(s2_dir / "session.json", "w") as f:
        json.dump({"id": "sess2", "state": "COMPLETED"}, f)
    with open(s2_dir / "activities.json", "w") as f:
        json.dump([{"id": "act2", "createTime": "2025-01-01T00:00:00Z"}], f)

    # part3 is missing! So sess3 is missing.

    # 1. Without --allow-partial -> Exit code 2 and DB intact (0 sessions in DB)
    ret_code_1 = import_jules_export([str(part1_dir), str(part2_dir)], owner="owner_test")
    assert ret_code_1 == 2

    sql_count = db.query(DBJulesSession).count()
    assert sql_count == 0

    # 2. With --allow-partial -> Exit code 3 and only present sessions (sess1, sess2) imported
    ret_code_2 = import_jules_export([str(part1_dir), str(part2_dir)], owner="owner_test", allow_partial=True)
    assert ret_code_2 == 3

    imported_sessions = db.query(DBJulesSession).all()
    imported_sids = sorted(s.session_id for s in imported_sessions)
    assert imported_sids == ["sess1", "sess2"]


def test_session_import_failure_handling(setup_test_db, tmp_path):
    db = setup_test_db

    export_dir = tmp_path / "export_fail"
    export_dir.mkdir()

    s1_dir = export_dir / "sessions" / "s1"
    s1_dir.mkdir(parents=True)
    with open(s1_dir / "session.json", "w") as f:
        json.dump({"id": "s1", "state": "COMPLETED"}, f)
    with open(s1_dir / "activities.json", "w") as f:
        json.dump([{"id": "act1"}], f)

    s2_dir = export_dir / "sessions" / "s2"
    s2_dir.mkdir(parents=True)
    with open(s2_dir / "session.json", "w") as f:
        json.dump({"id": "s2", "state": "COMPLETED"}, f)
    with open(s2_dir / "activities.json", "w") as f:
        json.dump([{"id": "act2"}], f)

    with open(export_dir / "sessions.json", "w") as f:
        json.dump([{"id": "s1"}, {"id": "s2"}], f)

    original_get_db_sync_session = get_db_sync_session

    def mock_get_db_sync_session():
        sess = original_get_db_sync_session()
        orig_commit = sess.commit

        def mock_commit():
            for obj in list(sess.new) + list(sess.dirty):
                if getattr(obj, "session_id", None) == "s2":
                    raise ValueError("Forced DB error on session s2")
            orig_commit()

        sess.commit = mock_commit
        return sess

    with patch("scripts.import_jules_export.get_db_sync_session", side_effect=mock_get_db_sync_session):
        ret_code = import_jules_export([str(export_dir)], owner="owner_test")

    assert ret_code == 1
    assert db.query(DBJulesSession).filter(DBJulesSession.session_id == "s1").first() is not None
    assert db.query(DBJulesSession).filter(DBJulesSession.session_id == "s2").first() is None


def test_duplicate_activity_ids_deduplication(setup_test_db, tmp_path):
    db = setup_test_db

    export_dir = tmp_path / "export_dup"
    export_dir.mkdir()

    s1_dir = export_dir / "sessions" / "s1"
    s1_dir.mkdir(parents=True)
    with open(s1_dir / "session.json", "w") as f:
        json.dump({"id": "s1", "state": "COMPLETED"}, f)
    with open(s1_dir / "activities.json", "w") as f:
        json.dump([
            {"id": "act_1", "createTime": "2025-01-01T10:00:00Z", "step": 1},
            {"id": "act_1", "createTime": "2025-01-01T10:05:00Z", "step": 2},  # Duplicate
            {"id": "act_2", "createTime": "2025-01-01T10:10:00Z", "step": 3}
        ], f)

    with open(export_dir / "sessions.json", "w") as f:
        json.dump([{"id": "s1"}], f)

    ret_code = import_jules_export([str(export_dir)], owner="owner_test")
    assert ret_code == 0

    acts = db.query(DBJulesActivity).filter(DBJulesActivity.session_id == "s1").order_by(DBJulesActivity.seq).all()
    assert len(acts) == 2
    assert acts[0].activity_id == "act_1"
    assert acts[0].payload.get("step") == 1  # First occurrence retained
    assert acts[1].activity_id == "act_2"


def test_faithful_source_fidelity_and_endpoint_omission(setup_test_db, tmp_path):
    db = setup_test_db

    export_dir = tmp_path / "export_sources"
    export_dir.mkdir()

    sources_data = [
        {
            "id": "github/no-branches-org/no-branches-repo",
            "githubRepo": {
                "owner": "no-branches-org",
                "repo": "no-branches-repo",
                "isPrivate": False
            }
        }
    ]
    with open(export_dir / "sources.json", "w") as f:
        json.dump(sources_data, f)

    with open(export_dir / "sessions.json", "w") as f:
        json.dump([], f)

    ret_code = import_jules_export([str(export_dir)], owner="owner_test")
    assert ret_code == 0

    # DB verification
    src = db.query(DBSource).filter(DBSource.name == "sources/github/no-branches-org/no-branches-repo").first()
    assert src is not None
    assert src.default_branch == ""
    assert src.branches == []

    # API endpoint verification
    full_key, key_hash, visible_prefix = generate_api_key()
    db.add(DBApiKey(key_id="k_src", key_hash=key_hash, visible_prefix=visible_prefix, owner="owner_test"))
    db.commit()

    client = TestClient(app)
    headers = {"x-goog-api-key": full_key}

    resp = client.get("/v1alpha/sources/github/no-branches-org/no-branches-repo", headers=headers)
    assert resp.status_code == 200
    gh_repo = resp.json()["githubRepo"]
    assert "defaultBranch" not in gh_repo
    assert "branches" not in gh_repo


def test_memory_footprint_tracemalloc(setup_test_db, tmp_path):
    db = setup_test_db

    export_dir = tmp_path / "export_large"
    export_dir.mkdir()

    sessions_list = []
    large_payload_chunk = "x" * 500_000  # ~500 KB chunk per session

    for i in range(100):
        sid = f"sess_{i:03d}"
        sessions_list.append({"id": sid})

        s_dir = export_dir / "sessions" / sid
        s_dir.mkdir(parents=True)

        with open(s_dir / "session.json", "w") as f:
            json.dump({"id": sid, "state": "COMPLETED", "data": large_payload_chunk}, f)
        with open(s_dir / "activities.json", "w") as f:
            json.dump([{"id": f"act_{i}", "data": large_payload_chunk}], f)

    with open(export_dir / "sessions.json", "w") as f:
        json.dump(sessions_list, f)

    tracemalloc.start()
    ret_code = import_jules_export([str(export_dir)], owner="owner_test")
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert ret_code == 0
    assert db.query(DBJulesSession).count() == 100

    # Peak memory overhead should be on the order of 1 session (< 5 MB)
    assert peak_mem < 5 * 1024 * 1024, f"Peak memory was too high: {peak_mem / 1024 / 1024:.2f} MB"
