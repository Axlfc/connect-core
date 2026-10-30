import os
import json
import pytest
import asyncio
from pathlib import Path
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
    import_jules_export([str(FIXTURE_DIR)], owner="owner_test_1")

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
    import_jules_export([str(FIXTURE_DIR)], owner="owner_test_1")

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
