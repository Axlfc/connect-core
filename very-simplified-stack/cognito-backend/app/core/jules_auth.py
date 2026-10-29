import hashlib
import hmac
import time
import secrets
import logging
from typing import Optional, Tuple
from fastapi import Request, HTTPException, status, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.models.db import DBApiKey

logger = logging.getLogger("cognito.jules.auth")

# Key format requirement: Must start with "cgk_", never "nvapi-" or "sk-"
KEY_PREFIX = "cgk_"

class JulesAPIError(HTTPException):
    def __init__(self, status_code: int, message: str, gcp_status: str):
        super().__init__(status_code=status_code, detail=message)
        self.status_code = status_code
        self.message = message
        self.gcp_status = gcp_status

def hash_api_key(key: str) -> str:
    """
    Computes SHA-256 hash of API key.
    """
    return hashlib.sha256(key.encode("utf-8")).hexdigest()

def generate_api_key(prefix: str = KEY_PREFIX) -> Tuple[str, str, str]:
    """
    Generates a new secure API key with prefix 'cgk_'.
    Returns: (full_key, key_hash, visible_prefix)
    Full key is only returned once when created.
    """
    raw_secret = secrets.token_hex(24)
    full_key = f"{prefix}{raw_secret}"
    key_hash = hash_api_key(full_key)
    visible_prefix = full_key[:10]  # e.g. "cgk_a1b2c3"
    return full_key, key_hash, visible_prefix

async def verify_jules_api_key(
    request: Request,
    db: AsyncSession = Depends(get_db_session)
) -> DBApiKey:
    """
    Authenticates requests under /v1alpha using 'x-goog-api-key' header or 'key' query parameter.
    Validates hash using constant-time comparison (hmac.compare_digest).
    Ensures keys are never logged.
    """
    api_key = request.headers.get("x-goog-api-key") or request.query_params.get("key")
    if not api_key:
        raise JulesAPIError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            message="Missing required x-goog-api-key header or key query parameter.",
            gcp_status="UNAUTHENTICATED"
        )

    clean_key = api_key.strip()
    provided_hash = hash_api_key(clean_key)

    # Lookup by provided_hash
    result = await db.execute(select(DBApiKey).where(DBApiKey.key_hash == provided_hash))
    key_obj = result.scalars().first()

    if not key_obj:
        # Perform dummy hmac comparison to prevent timing leaks
        dummy_hash = hash_api_key("cgk_dummy_key_for_timing_protection_00000000")
        hmac.compare_digest(provided_hash, dummy_hash)
        raise JulesAPIError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            message="Invalid API key provided.",
            gcp_status="UNAUTHENTICATED"
        )

    # Constant-time comparison
    if not hmac.compare_digest(key_obj.key_hash, provided_hash):
        raise JulesAPIError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            message="Invalid API key provided.",
            gcp_status="UNAUTHENTICATED"
        )

    if key_obj.is_revoked:
        raise JulesAPIError(
            status_code=status.HTTP_403_FORBIDDEN,
            message="The provided API key has been revoked.",
            gcp_status="PERMISSION_DENIED"
        )

    # Update last_used_at timestamp
    key_obj.last_used_at = time.time()
    await db.commit()

    return key_obj
