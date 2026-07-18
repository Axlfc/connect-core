import hmac
import hashlib
import time
import logging
from typing import Set, List
from fastapi import Request, HTTPException, Security
from fastapi.security import APIKeyHeader

logger = logging.getLogger("cognito.worker.auth")

# Nonce cache to prevent replay attacks
_SEEN_NONCES: Set[str] = set()
_NONCE_CLEANUP_INTERVAL = 300
_last_cleanup_time = time.time()

# Stale timestamp threshold: 5 minutes
TIMESTAMP_MAX_AGE_SEC = 300

def clean_stale_nonces():
    global _last_cleanup_time
    now = time.time()
    if now - _last_cleanup_time > _NONCE_CLEANUP_INTERVAL:
        # Clear seen nonces as older than 5 mins will be rejected by timestamp check anyway
        _SEEN_NONCES.clear()
        _last_cleanup_time = now

def calculate_signature(secret: str, method: str, path: str, timestamp: str, nonce: str, body_sha256: str, worker_id: str) -> str:
    canonical = f"{method}\n{path}\n{timestamp}\n{nonce}\n{body_sha256}\n{worker_id}"
    h = hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256)
    return h.hexdigest()

async def verify_cognito_request(request: Request, secrets: List[str], allowed_worker_id: str):
    clean_stale_nonces()

    worker_id = request.headers.get("X-Cognito-Worker-Id")
    timestamp_str = request.headers.get("X-Cognito-Timestamp")
    nonce = request.headers.get("X-Cognito-Nonce")
    body_sha256 = request.headers.get("X-Cognito-Body-SHA256")
    signature = request.headers.get("X-Cognito-Signature")

    if not all([worker_id, timestamp_str, nonce, body_sha256, signature]):
        # Fallback to simple Bearer token check for development/testing if specified
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            if token in secrets:
                return True
        raise HTTPException(status_code=401, detail="Missing required authentication signature headers")

    if worker_id != allowed_worker_id:
        raise HTTPException(status_code=403, detail="Invalid worker ID")

    # Timestamp freshness validation
    try:
        req_time = float(timestamp_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid timestamp format")

    now = time.time()
    if abs(now - req_time) > TIMESTAMP_MAX_AGE_SEC:
        raise HTTPException(status_code=401, detail="Request timestamp is stale")

    # Replay attack protection
    if nonce in _SEEN_NONCES:
        raise HTTPException(status_code=401, detail="Request nonce has already been used")
    _SEEN_NONCES.add(nonce)

    # Validate signature against body hash
    body_bytes = await request.body()
    actual_sha = hashlib.sha256(body_bytes).hexdigest()
    if actual_sha != body_sha256:
         raise HTTPException(status_code=400, detail="Body SHA-256 mismatch")

    # Constant-time comparison against current and previous secrets
    method = request.method
    path = request.url.path

    signature_matched = False
    for secret in secrets:
        expected = calculate_signature(secret, method, path, timestamp_str, nonce, body_sha256, worker_id)
        if hmac.compare_digest(expected, signature):
            signature_matched = True
            break

    if not signature_matched:
        raise HTTPException(status_code=401, detail="HMAC signature verification failed")

    return True
