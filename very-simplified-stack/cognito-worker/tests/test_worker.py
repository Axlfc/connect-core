import pytest
import os
import time
import hashlib
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient

from worker_app.main import app, worktree_manager, ALLOWED_ROOTS, WORKER_ID, SHARED_SECRETS
from worker_app.auth import calculate_signature

@pytest.fixture
def client():
    # Make sure tempfile directory is allowed
    tmp_real = os.path.realpath(tempfile.gettempdir())
    if tmp_real not in ALLOWED_ROOTS:
        ALLOWED_ROOTS.append(tmp_real)
    return TestClient(app)

def test_worker_health(client):
    resp = client.get("/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["worker_id"] == WORKER_ID

def test_hmac_authentication(client):
    # Test unauthorized request
    resp = client.get("/v1/models")
    assert resp.status_code == 401

    # Test authorized request
    timestamp = str(time.time())
    nonce = f"nonce-{time.time()}"
    body_sha256 = hashlib.sha256(b"").hexdigest()

    # Calculate valid signature
    sig = calculate_signature(
        SHARED_SECRETS[0], "GET", "/v1/models", timestamp, nonce, body_sha256, WORKER_ID
    )

    headers = {
        "X-Cognito-Worker-Id": WORKER_ID,
        "X-Cognito-Timestamp": timestamp,
        "X-Cognito-Nonce": nonce,
        "X-Cognito-Body-SHA256": body_sha256,
        "X-Cognito-Signature": sig
    }

    resp = client.get("/v1/models", headers=headers)
    assert resp.status_code == 200
    assert "models" in resp.json()

def test_stale_timestamp_hmac(client):
    # 10 minutes ago
    timestamp = str(time.time() - 600)
    nonce = f"nonce-{time.time()}"
    body_sha256 = hashlib.sha256(b"").hexdigest()

    sig = calculate_signature(
        SHARED_SECRETS[0], "GET", "/v1/models", timestamp, nonce, body_sha256, WORKER_ID
    )

    headers = {
        "X-Cognito-Worker-Id": WORKER_ID,
        "X-Cognito-Timestamp": timestamp,
        "X-Cognito-Nonce": nonce,
        "X-Cognito-Body-SHA256": body_sha256,
        "X-Cognito-Signature": sig
    }

    resp = client.get("/v1/models", headers=headers)
    assert resp.status_code == 401
    assert "timestamp is stale" in resp.json()["detail"]

def test_nonce_replay_protection(client):
    timestamp = str(time.time())
    nonce = f"nonce-replay-{time.time()}"
    body_sha256 = hashlib.sha256(b"").hexdigest()

    sig = calculate_signature(
        SHARED_SECRETS[0], "GET", "/v1/models", timestamp, nonce, body_sha256, WORKER_ID
    )

    headers = {
        "X-Cognito-Worker-Id": WORKER_ID,
        "X-Cognito-Timestamp": timestamp,
        "X-Cognito-Nonce": nonce,
        "X-Cognito-Body-SHA256": body_sha256,
        "X-Cognito-Signature": sig
    }

    # First request
    resp = client.get("/v1/models", headers=headers)
    assert resp.status_code == 200

    # Second request with same nonce
    resp2 = client.get("/v1/models", headers=headers)
    assert resp2.status_code == 401
    assert "nonce has already been used" in resp2.json()["detail"]
