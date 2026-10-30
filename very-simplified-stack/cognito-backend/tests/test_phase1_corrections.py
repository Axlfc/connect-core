import os
import sys
import json
import base64
import zipfile
import pytest
import subprocess
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.database import get_db_session, get_db_sync_session
from app.models.db import DBJulesSession, DBJulesActivity, DBSource, DBApiKey
from app.core.jules_auth import generate_api_key
from app.api.routes.jules_v1alpha import encode_page_token, decode_page_token
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
    db.query(DBJulesActivity).delete()
    db.query(DBJulesSession).delete()
    db.query(DBSource).delete()
    db.query(DBApiKey).delete()
    db.commit()
    yield db


def test_query_param_key_rejected_401(setup_test_db):
    db = setup_test_db
    full_key, key_hash, visible_prefix = generate_api_key()
    api_key_obj = DBApiKey(
        key_id="key_qparam",
        key_hash=key_hash,
        visible_prefix=visible_prefix,
        owner="owner_qparam"
    )
    db.add(api_key_obj)
    db.commit()

    client = TestClient(app)

    # 1. Query parameter ?key=... must be rejected with 401 UNAUTHENTICATED
    resp_qparam = client.get(f"/v1alpha/sessions?key={full_key}")
    assert resp_qparam.status_code == 401
    err = resp_qparam.json()["error"]
    assert err["code"] == 401
    assert err["status"] == "UNAUTHENTICATED"
    assert "Missing required x-goog-api-key header" in err["message"]

    # 2. Header authentication works
    resp_hdr = client.get("/v1alpha/sessions", headers={"x-goog-api-key": full_key})
    assert resp_hdr.status_code == 200


def test_pagination_tokens_and_offset_validation(setup_test_db):
    client = TestClient(app)

    # 1. URL-safe base64 encoding without padding
    token = encode_page_token(30)
    assert "=" not in token
    assert decode_page_token(token) == 30

    # 2. Unpadded token decoding simulation
    decoded_offset = decode_page_token(token)
    assert decoded_offset == 30

    # 3. Old standard base64 token support
    legacy_json = json.dumps({"offset": 60}).encode("utf-8")
    legacy_token = base64.b64encode(legacy_json).decode("utf-8")
    assert decode_page_token(legacy_token) == 60

    # 4. Invalid tokens raise 400 INVALID_ARGUMENT in Jules format
    with pytest.raises(Exception) as exc_info:
        decode_page_token("garbage_token_!!!")
    assert getattr(exc_info.value, "status_code", None) == 400

    # Negative offset token
    neg_token = base64.urlsafe_b64encode(json.dumps({"offset": -10}).encode("utf-8")).decode("utf-8")
    with pytest.raises(Exception) as exc_info_neg:
        decode_page_token(neg_token)
    assert getattr(exc_info_neg.value, "status_code", None) == 400

    # Oversized offset token (> 10_000_000)
    over_token = base64.urlsafe_b64encode(json.dumps({"offset": 20_000_000}).encode("utf-8")).decode("utf-8")
    with pytest.raises(Exception) as exc_info_over:
        decode_page_token(over_token)
    assert getattr(exc_info_over.value, "status_code", None) == 400


def test_v1alpha_validation_422_mapped_to_400_invalid_argument(setup_test_db):
    db = setup_test_db
    full_key, key_hash, visible_prefix = generate_api_key()
    api_key_obj = DBApiKey(
        key_id="key_val",
        key_hash=key_hash,
        visible_prefix=visible_prefix,
        owner="owner_val"
    )
    db.add(api_key_obj)
    db.commit()

    client = TestClient(app)

    # Calling /v1alpha endpoint with invalid query parameter (pageSize=abc)
    resp = client.get("/v1alpha/sessions?pageSize=abc", headers={"x-goog-api-key": full_key})
    assert resp.status_code == 400
    err = resp.json()["error"]
    assert err["code"] == 400
    assert err["status"] == "INVALID_ARGUMENT"
    assert "Invalid argument" in err["message"]


def test_sources_endpoint_omits_is_private_when_false(setup_test_db):
    db = setup_test_db

    # Public source
    pub_src = DBSource(
        name="sources/github/hypenosys/hypenosys.github.io",
        id="github/hypenosys/hypenosys.github.io",
        owner="hypenosys",
        repo="hypenosys.github.io",
        is_private=False,
        default_branch="main",
        branches=["main"]
    )
    # Private source
    priv_src = DBSource(
        name="sources/github/Axlfc/1337",
        id="github/Axlfc/1337",
        owner="Axlfc",
        repo="1337",
        is_private=True,
        default_branch="main",
        branches=["main", "dev"]
    )
    db.add(pub_src)
    db.add(priv_src)

    full_key, key_hash, visible_prefix = generate_api_key()
    api_key_obj = DBApiKey(
        key_id="key_src",
        key_hash=key_hash,
        visible_prefix=visible_prefix,
        owner="owner_src"
    )
    db.add(api_key_obj)
    db.commit()

    client = TestClient(app)
    headers = {"x-goog-api-key": full_key}

    resp = client.get("/v1alpha/sources", headers=headers)
    assert resp.status_code == 200
    sources = resp.json()["sources"]
    assert len(sources) == 2

    for s in sources:
        gh = s["githubRepo"]
        if gh["owner"] == "hypenosys":
            # isPrivate must be omitted when False
            assert "isPrivate" not in gh
        elif gh["owner"] == "Axlfc":
            assert gh.get("isPrivate") is True


def test_zip_imports_idempotency_and_manifest_completeness(setup_test_db, tmp_path):
    db = setup_test_db

    # Build synthetic ZIP files part01.zip and index.zip
    part01_path = tmp_path / "part01.zip"
    index_path = tmp_path / "index.zip"

    session_payload = {
        "id": "sess_zip_1",
        "createTime": "2025-02-01T12:00:00.000000000Z",
        "updateTime": "2025-02-01T12:05:00.000000000Z",
        "state": "COMPLETED",
        "sourceContext": {"source": "sources/github/Axlfc/1337"}
    }
    activity_payload = {
        "id": "act_zip_1",
        "createTime": "2025-02-01T12:01:00.000000000Z",
        "originator": "user"
    }

    # Write part01.zip containing sessions/sess_zip_1/(session.json|activities.json)
    with zipfile.ZipFile(part01_path, "w") as z1:
        z1.writestr("jules-export-2025-02-01/sessions/sess_zip_1/session.json", json.dumps(session_payload))
        z1.writestr("jules-export-2025-02-01/sessions/sess_zip_1/activities.json", json.dumps([activity_payload]))

    sources_payload = [
        {
            "id": "github/Axlfc/1337",
            "githubRepo": {
                "owner": "Axlfc",
                "repo": "1337",
                "isPrivate": True,
                "defaultBranch": {"displayName": "main"},
                "branches": [{"displayName": "main"}]
            }
        }
    ]
    manifest_payload = {
        "sessions_by_part": {
            "part01.zip": ["sess_zip_1"]
        }
    }

    # Write index.zip containing sources.json, sessions.json, manifest.json
    with zipfile.ZipFile(index_path, "w") as z2:
        z2.writestr("jules-export-2025-02-01/sources.json", json.dumps(sources_payload))
        z2.writestr("jules-export-2025-02-01/sessions.json", json.dumps([session_payload]))
        z2.writestr("jules-export-2025-02-01/manifest.json", json.dumps(manifest_payload))

    # 1. Dry run execution
    res_dry = import_jules_export([str(part01_path), str(index_path)], owner="zip_owner", dry_run=True)
    assert res_dry == 0
    assert db.query(DBJulesSession).count() == 0

    # 2. First real import from ZIPs
    res_1 = import_jules_export([str(part01_path), str(index_path)], owner="zip_owner", dry_run=False)
    assert res_1 == 0
    assert db.query(DBJulesSession).count() == 1
    assert db.query(DBJulesActivity).count() == 1
    assert db.query(DBSource).count() == 1

    # 3. Second import (idempotency check, no duplicates)
    res_2 = import_jules_export([str(part01_path), str(index_path)], owner="zip_owner", dry_run=False)
    assert res_2 == 0
    assert db.query(DBJulesSession).count() == 1
    assert db.query(DBJulesActivity).count() == 1
    assert db.query(DBSource).count() == 1

    # 4. Manifest completeness check failure
    broken_index_path = tmp_path / "broken_index.zip"
    broken_manifest = {
        "sessions_by_part": {
            "part01.zip": ["sess_zip_1", "sess_missing_999"]
        }
    }
    with zipfile.ZipFile(broken_index_path, "w") as zb:
        zb.writestr("sources.json", json.dumps(sources_payload))
        zb.writestr("sessions.json", json.dumps([session_payload]))
        zb.writestr("manifest.json", json.dumps(broken_manifest))

    res_broken = import_jules_export([str(part01_path), str(broken_index_path)], owner="zip_owner", dry_run=False)
    assert res_broken != 0


def test_create_jules_api_key_script(setup_test_db, tmp_path):
    script_path = Path(__file__).parent.parent / "scripts" / "create_jules_api_key.py"
    db_file = tmp_path / "test_cli.db"

    # Creation
    env = os.environ.copy()
    env["COGNITO_DATABASE_URL"] = f"sqlite+aiosqlite:///{db_file}"
    proc = subprocess.run(
        [sys.executable, str(script_path), "--owner", "cli_user"],
        capture_output=True,
        text=True,
        env=env
    )
    assert proc.returncode == 0
    assert "API KEY CREATED SUCCESSFULLY" in proc.stdout
    assert "cgk_" in proc.stdout

    # List
    proc_list = subprocess.run(
        [sys.executable, str(script_path), "--list"],
        capture_output=True,
        text=True,
        env=env
    )
    assert proc_list.returncode == 0
    assert "cli_user" in proc_list.stdout
    assert "cgk_" in proc_list.stdout

    # Extract visible prefix from process output or query file
    prefix = None
    for line in proc.stdout.splitlines():
        if "Visible Prefix:" in line:
            prefix = line.split(":")[-1].strip()
    assert prefix is not None

    # Revoke
    proc_revoke = subprocess.run(
        [sys.executable, str(script_path), "--revoke", prefix],
        capture_output=True,
        text=True,
        env=env
    )
    assert proc_revoke.returncode == 0
    assert f"Successfully revoked 1 API key(s) with visible prefix '{prefix}'" in proc_revoke.stdout
