import os
import time
import json
import zipfile
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.database import get_db_session, get_db_sync_session
from app.models.db import DBJulesSession, DBJulesActivity, DBSource, DBApiKey
from app.core.jules_auth import generate_api_key
from scripts.export_jules_sessions import export_jules_sessions


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

    def add(self, obj):
        self._sync.add(obj)


async def override_get_db_session():
    sync_sess = get_db_sync_session()
    try:
        yield SyncToAsyncSessionAdapter(sync_sess)
    finally:
        sync_sess.close()

app.dependency_overrides[get_db_session] = override_get_db_session


@pytest.fixture(autouse=True)
def setup_jules_engine_db():
    with get_db_sync_session() as db:
        db.query(DBJulesActivity).delete()
        db.query(DBJulesSession).delete()
        db.query(DBSource).delete()
        db.query(DBApiKey).delete()
        db.commit()
    yield
    with get_db_sync_session() as db:
        db.query(DBJulesActivity).delete()
        db.query(DBJulesSession).delete()
        db.query(DBSource).delete()
        db.query(DBApiKey).delete()
        db.commit()


def test_post_sessions_creation_and_background_execution(tmp_path):
    # Setup API Key
    with get_db_sync_session() as db:
        full_key, key_hash, visible_prefix = generate_api_key()
        api_key_obj = DBApiKey(
            key_id="key_eng_1",
            key_hash=key_hash,
            visible_prefix=visible_prefix,
            owner="eng_user_1"
        )
        db.add(api_key_obj)

        source_obj = DBSource(
            name="sources/github/Axlfc/connect-core",
            id="github/Axlfc/connect-core",
            owner="Axlfc",
            repo="connect-core",
            is_private=False,
            default_branch="master",
            branches=["master"]
        )
        db.add(source_obj)
        db.commit()

    client = TestClient(app)
    headers = {"x-goog-api-key": full_key}

    # 1. Validation error on empty prompt
    resp_empty = client.post("/v1alpha/sessions", headers=headers, json={"prompt": "  "})
    assert resp_empty.status_code == 400
    assert resp_empty.json()["error"]["status"] == "INVALID_ARGUMENT"

    # 2. Valid POST /v1alpha/sessions
    payload = {
        "title": "Autonomous bugfix test",
        "prompt": "Fix bug in greeting logic",
        "sourceContext": {
            "source": "sources/github/Axlfc/connect-core",
            "githubRepoContext": {
                "startingBranch": "master"
            }
        }
    }

    resp = client.post("/v1alpha/sessions", headers=headers, json=payload)
    assert resp.status_code == 200
    sess_data = resp.json()
    assert sess_data["title"] == "Autonomous bugfix test"
    assert sess_data["prompt"] == "Fix bug in greeting logic"
    assert sess_data["state"] in ["QUEUED", "RUNNING", "COMPLETED"]
    session_id = sess_data["id"]

    # 3. Verify session persisted in DB
    with get_db_sync_session() as db:
        db_s = db.query(DBJulesSession).filter(DBJulesSession.session_id == session_id).first()
        assert db_s is not None
        assert db_s.owner == "eng_user_1"

    # 4. Test GET /v1alpha/sessions/{session_id}
    resp_get = client.get(f"/v1alpha/sessions/{session_id}", headers=headers)
    assert resp_get.status_code == 200
    assert resp_get.json()["id"] == session_id


def test_send_message_steering(tmp_path):
    with get_db_sync_session() as db:
        full_key, key_hash, visible_prefix = generate_api_key()
        api_key_obj = DBApiKey(
            key_id="key_eng_2",
            key_hash=key_hash,
            visible_prefix=visible_prefix,
            owner="eng_user_2"
        )
        db.add(api_key_obj)

        session_id = "test_steer_sess_1"
        db_session = DBJulesSession(
            session_id=session_id,
            payload={
                "name": f"sessions/{session_id}",
                "id": session_id,
                "title": "Steering Test Session",
                "prompt": "Initial prompt",
                "state": "RUNNING",
                "url": f"https://jules.google/sessions/{session_id}",
                "createTime": "2026-10-31T10:00:00.000000Z",
                "updateTime": "2026-10-31T10:00:00.000000Z",
                "outputs": []
            },
            create_time="2026-10-31T10:00:00.000000Z",
            update_time="2026-10-31T10:00:00.000000Z",
            state="RUNNING",
            source="sources/github/Axlfc/connect-core",
            owner="eng_user_2"
        )
        db.add(db_session)
        db.commit()

    client = TestClient(app)
    headers = {"x-goog-api-key": full_key}

    # 1. Invalid message
    resp_err = client.post(f"/v1alpha/sessions/{session_id}:sendMessage", headers=headers, json={"message": ""})
    assert resp_err.status_code == 400
    assert resp_err.json()["error"]["status"] == "INVALID_ARGUMENT"

    # 2. Valid steering message
    resp_ok = client.post(
        f"/v1alpha/sessions/{session_id}:sendMessage",
        headers=headers,
        json={"message": "Please make sure to add type annotations"}
    )
    assert resp_ok.status_code == 200
    act_data = resp_ok.json()
    assert act_data["originator"] == "user"
    assert act_data["userMessaged"]["userMessage"] == "Please make sure to add type annotations"

    # 3. Check activity persisted in DB
    with get_db_sync_session() as db:
        acts = db.query(DBJulesActivity).filter(DBJulesActivity.session_id == session_id).all()
        assert len(acts) == 1
        assert acts[0].payload["userMessaged"]["userMessage"] == "Please make sure to add type annotations"


def test_export_jules_sessions_canonical(tmp_path):
    with get_db_sync_session() as db:
        source_obj = DBSource(
            name="sources/github/Axlfc/connect-core",
            id="github/Axlfc/connect-core",
            owner="Axlfc",
            repo="connect-core",
            is_private=False,
            default_branch="master",
            branches=["master"]
        )
        db.add(source_obj)

        sid = "export_sess_001"
        db_s = DBJulesSession(
            session_id=sid,
            payload={
                "name": f"sessions/{sid}",
                "id": sid,
                "title": "Export Test",
                "prompt": "Test export",
                "state": "COMPLETED",
                "url": f"https://jules.google/sessions/{sid}",
                "createTime": "2026-10-31T12:00:00.000000Z",
                "updateTime": "2026-10-31T12:05:00.000000Z",
                "outputs": []
            },
            create_time="2026-10-31T12:00:00.000000Z",
            update_time="2026-10-31T12:05:00.000000Z",
            state="COMPLETED",
            source="sources/github/Axlfc/connect-core",
            owner="export_user"
        )
        db.add(db_s)

        db_act = DBJulesActivity(
            session_id=sid,
            activity_id="act-001",
            seq=1,
            payload={
                "name": f"sessions/{sid}/activities/act-001",
                "id": "act-001",
                "originator": "user",
                "createTime": "2026-10-31T12:00:00.000000Z",
                "userMessaged": {"userMessage": "Test export"}
            },
            originator="user",
            create_time="2026-10-31T12:00:00.000000Z"
        )
        db.add(db_act)
        db.commit()

    # 1. Export as ZIP
    zip_path = tmp_path / "export.zip"
    ret = export_jules_sessions(output_path=str(zip_path), owner="export_user", output_format="zip")
    assert ret == 0
    assert zip_path.exists()

    with zipfile.ZipFile(zip_path, "r") as zf:
        namelist = zf.namelist()
        assert any(n.endswith("manifest.json") for n in namelist)
        assert any(n.endswith("sources.json") for n in namelist)
        assert any(n.endswith("sessions.json") for n in namelist)
        assert any(n.endswith(f"sessions/{sid}/session.json") for n in namelist)
        assert any(n.endswith(f"sessions/{sid}/activities.json") for n in namelist)

    # 2. Export as directory
    dir_path = tmp_path / "export_dir"
    ret_dir = export_jules_sessions(output_path=str(dir_path), owner="export_user", output_format="dir")
    assert ret_dir == 0
    found_manifest = list(dir_path.glob("**/manifest.json"))
    assert len(found_manifest) == 1
