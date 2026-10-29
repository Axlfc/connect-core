import re
import json
import base64
import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Request, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.future import select
from sqlalchemy import func, asc, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.models.db import DBJulesSession, DBJulesActivity, DBSource, DBApiKey
from app.core.jules_auth import verify_jules_api_key, JulesAPIError

logger = logging.getLogger("cognito.jules.v1alpha")

router = APIRouter(prefix="/v1alpha", tags=["Jules API v1alpha"])

SESSION_ID_REGEX = re.compile(r"^[0-9A-Za-z_-]+$")

def validate_session_id(session_id: str) -> None:
    """
    Validates session ID format.
    If session ID contains invalid characters (e.g., ':'), returns 404 NOT_FOUND per contract.
    """
    if not SESSION_ID_REGEX.match(session_id):
        raise JulesAPIError(
            status_code=status.HTTP_404_NOT_FOUND,
            message=f"Resource 'sessions/{session_id}' not found.",
            gcp_status="NOT_FOUND"
        )

def encode_page_token(offset: int) -> str:
    payload = json.dumps({"offset": offset}).encode("utf-8")
    return base64.b64encode(payload).decode("utf-8")

def decode_page_token(token: str) -> int:
    try:
        raw = base64.b64decode(token.encode("utf-8")).decode("utf-8")
        data = json.loads(raw)
        return int(data.get("offset", 0))
    except Exception:
        raise JulesAPIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"Invalid pageToken provided: '{token}'",
            gcp_status="INVALID_ARGUMENT"
        )

# Exception response utility
def jules_error_response(code: int, message: str, gcp_status: str) -> JSONResponse:
    return JSONResponse(
        status_code=code,
        content={
            "error": {
                "code": code,
                "message": message,
                "status": gcp_status
            }
        }
    )

# SOURCES ENDPOINTS
@router.get("/sources")
async def list_sources(
    pageSize: int = Query(30),
    pageToken: Optional[str] = Query(None),
    api_key: DBApiKey = Depends(verify_jules_api_key),
    db: AsyncSession = Depends(get_db_session)
):
    if pageSize < 1 or pageSize > 100:
        raise JulesAPIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"pageSize must be between 1 and 100. Got {pageSize}.",
            gcp_status="INVALID_ARGUMENT"
        )

    offset = decode_page_token(pageToken) if pageToken else 0

    query = select(DBSource).order_by(asc(DBSource.name)).offset(offset).limit(pageSize + 1)
    result = await db.execute(query)
    sources_rows = result.scalars().all()

    next_page_token = None
    if len(sources_rows) > pageSize:
        next_page_token = encode_page_token(offset + pageSize)
        sources_rows = sources_rows[:pageSize]

    sources_list = []
    for s in sources_rows:
        sources_list.append({
            "name": s.name,
            "id": s.id,
            "githubRepo": {
                "owner": s.owner,
                "repo": s.repo,
                "isPrivate": s.is_private,
                "defaultBranch": {"displayName": s.default_branch},
                "branches": [{"displayName": b} if isinstance(b, str) else b for b in (s.branches or [])]
            }
        })

    resp = {"sources": sources_list}
    if next_page_token:
        resp["nextPageToken"] = next_page_token
    return resp

@router.get("/sources/{source_path:path}")
async def get_source(
    source_path: str,
    api_key: DBApiKey = Depends(verify_jules_api_key),
    db: AsyncSession = Depends(get_db_session)
):
    clean_path = source_path.strip()
    if not clean_path.startswith("sources/"):
        clean_path = f"sources/{clean_path}"

    result = await db.execute(select(DBSource).where(DBSource.name == clean_path))
    s = result.scalars().first()

    if not s:
        raise JulesAPIError(
            status_code=status.HTTP_404_NOT_FOUND,
            message=f"Source '{clean_path}' not found.",
            gcp_status="NOT_FOUND"
        )

    return {
        "name": s.name,
        "id": s.id,
        "githubRepo": {
            "owner": s.owner,
            "repo": s.repo,
            "isPrivate": s.is_private,
            "defaultBranch": {"displayName": s.default_branch},
            "branches": [{"displayName": b} if isinstance(b, str) else b for b in (s.branches or [])]
        }
    }

# SESSIONS ENDPOINTS
@router.get("/sessions")
async def list_sessions(
    pageSize: int = Query(30),
    pageToken: Optional[str] = Query(None),
    api_key: DBApiKey = Depends(verify_jules_api_key),
    db: AsyncSession = Depends(get_db_session)
):
    if pageSize < 1 or pageSize > 100:
        raise JulesAPIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"pageSize must be between 1 and 100. Got {pageSize}.",
            gcp_status="INVALID_ARGUMENT"
        )

    offset = decode_page_token(pageToken) if pageToken else 0

    # Scoped to API key owner
    query = (
        select(DBJulesSession)
        .where(DBJulesSession.owner == api_key.owner)
        .order_by(desc(DBJulesSession.create_time), desc(DBJulesSession.session_id))
        .offset(offset)
        .limit(pageSize + 1)
    )
    result = await db.execute(query)
    sessions_rows = result.scalars().all()

    next_page_token = None
    if len(sessions_rows) > pageSize:
        next_page_token = encode_page_token(offset + pageSize)
        sessions_rows = sessions_rows[:pageSize]

    sessions_list = [s.payload for s in sessions_rows]

    resp = {"sessions": sessions_list}
    if next_page_token:
        resp["nextPageToken"] = next_page_token
    return resp

@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    api_key: DBApiKey = Depends(verify_jules_api_key),
    db: AsyncSession = Depends(get_db_session)
):
    validate_session_id(session_id)

    result = await db.execute(select(DBJulesSession).where(DBJulesSession.session_id == session_id))
    s = result.scalars().first()

    if not s or s.owner != api_key.owner:
        raise JulesAPIError(
            status_code=status.HTTP_404_NOT_FOUND,
            message=f"Session 'sessions/{session_id}' not found.",
            gcp_status="NOT_FOUND"
        )

    return s.payload

# ACTIVITIES ENDPOINTS
@router.get("/sessions/{session_id}/activities")
async def list_activities(
    session_id: str,
    pageSize: int = Query(50),
    pageToken: Optional[str] = Query(None),
    createTime: Optional[str] = Query(None),
    api_key: DBApiKey = Depends(verify_jules_api_key),
    db: AsyncSession = Depends(get_db_session)
):
    validate_session_id(session_id)

    # First verify session ownership
    sess_result = await db.execute(select(DBJulesSession).where(DBJulesSession.session_id == session_id))
    s = sess_result.scalars().first()
    if not s or s.owner != api_key.owner:
        raise JulesAPIError(
            status_code=status.HTTP_404_NOT_FOUND,
            message=f"Session 'sessions/{session_id}' not found.",
            gcp_status="NOT_FOUND"
        )

    if pageSize < 1 or pageSize > 100:
        raise JulesAPIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"pageSize must be between 1 and 100. Got {pageSize}.",
            gcp_status="INVALID_ARGUMENT"
        )

    offset = decode_page_token(pageToken) if pageToken else 0

    query = select(DBJulesActivity).where(DBJulesActivity.session_id == session_id)
    if createTime:
        query = query.where(DBJulesActivity.create_time >= createTime)

    # Ordered from oldest to newest
    query = query.order_by(asc(DBJulesActivity.seq), asc(DBJulesActivity.create_time)).offset(offset).limit(pageSize + 1)

    result = await db.execute(query)
    activities_rows = result.scalars().all()

    next_page_token = None
    if len(activities_rows) > pageSize:
        next_page_token = encode_page_token(offset + pageSize)
        activities_rows = activities_rows[:pageSize]

    activities_list = [a.payload for a in activities_rows]

    resp = {"activities": activities_list}
    if next_page_token:
        resp["nextPageToken"] = next_page_token
    return resp
