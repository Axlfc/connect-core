import re
import json
import base64
import asyncio
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

MAX_OFFSET = 10_000_000

def encode_page_token(offset: int) -> str:
    payload = json.dumps({"offset": offset}).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("utf-8").rstrip("=")

def decode_page_token(token: str) -> int:
    if not token or not isinstance(token, str):
        raise JulesAPIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="Invalid pageToken provided.",
            gcp_status="INVALID_ARGUMENT"
        )

    padding_needed = -len(token) % 4
    padded_token = token + ("=" * padding_needed)

    raw_json = None
    try:
        raw_bytes = base64.urlsafe_b64decode(padded_token.encode("utf-8"))
        raw_json = raw_bytes.decode("utf-8")
    except Exception:
        try:
            raw_bytes = base64.b64decode(padded_token.encode("utf-8"))
            raw_json = raw_bytes.decode("utf-8")
        except Exception:
            pass

    if raw_json is None:
        raise JulesAPIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"Invalid pageToken provided: '{token}'",
            gcp_status="INVALID_ARGUMENT"
        )

    try:
        data = json.loads(raw_json)
        if not isinstance(data, dict) or "offset" not in data:
            raise ValueError("Missing offset field")

        offset = data["offset"]
        if isinstance(offset, bool) or not isinstance(offset, int):
            raise ValueError("Offset must be an integer")

        if offset < 0 or offset > MAX_OFFSET:
            raise ValueError(f"Offset {offset} out of bounds (0 <= offset <= {MAX_OFFSET})")

        return offset
    except Exception as e:
        raise JulesAPIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"Invalid pageToken provided: '{token}' ({str(e)})",
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
        gh_repo = {
            "owner": s.owner,
            "repo": s.repo,
        }
        if s.default_branch:
            gh_repo["defaultBranch"] = {"displayName": s.default_branch}
        if s.branches:
            gh_repo["branches"] = [{"displayName": b} if isinstance(b, str) else b for b in s.branches]
        if s.is_private:
            gh_repo["isPrivate"] = True

        sources_list.append({
            "name": s.name,
            "id": s.id,
            "githubRepo": gh_repo
        })

    resp = {"sources": sources_list}
    if next_page_token:
        resp["nextPageToken"] = next_page_token
    return resp

@router.post("/sessions/{session_id}:sendMessage")
async def send_session_message(
    session_id: str,
    request: Request,
    api_key: DBApiKey = Depends(verify_jules_api_key),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Sends a steering message to an ongoing Jules session.
    Injects message into session steering queue and records userMessaged activity.
    """
    validate_session_id(session_id)

    # Verify session ownership
    sess_result = await db.execute(select(DBJulesSession).where(DBJulesSession.session_id == session_id))
    s = sess_result.scalars().first()
    if not s or s.owner != api_key.owner:
        raise JulesAPIError(
            status_code=status.HTTP_404_NOT_FOUND,
            message=f"Session 'sessions/{session_id}' not found.",
            gcp_status="NOT_FOUND"
        )

    try:
        body = await request.json()
    except Exception:
        raise JulesAPIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="Invalid JSON request body.",
            gcp_status="INVALID_ARGUMENT"
        )

    user_msg = body.get("message") or body.get("userMessage") or body.get("prompt")
    if not user_msg or not isinstance(user_msg, str) or not user_msg.strip():
        raise JulesAPIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="Field 'message' or 'prompt' is required and must not be empty.",
            gcp_status="INVALID_ARGUMENT"
        )

    from app.services.jules_engine import now_iso
    from app.core.steering import steering_manager
    from app.core.session_manager import SessionManager
    import uuid

    # 1. Enqueue steering if cognito_session_id is active
    if s.cognito_session_id:
        try:
            sm = SessionManager()
            await steering_manager.post_steering_message(s.cognito_session_id, user_msg, session_manager=sm)
        except Exception as e:
            logger.warning(f"Could not post steering message to cognito session {s.cognito_session_id}: {e}")

    # 2. Record userMessaged activity
    # Calculate next sequence number
    count_res = await db.execute(
        select(func.count()).select_from(DBJulesActivity).where(DBJulesActivity.session_id == session_id)
    )
    current_count = count_res.scalar() or 0
    seq_number = current_count + 1

    act_id = f"msg-steer-{uuid.uuid4().hex[:12]}"
    act_time = now_iso()
    act_payload = {
        "name": f"sessions/{session_id}/activities/{act_id}",
        "id": act_id,
        "originator": "user",
        "createTime": act_time,
        "userMessaged": {
            "userMessage": user_msg
        }
    }

    db_act = DBJulesActivity(
        session_id=session_id,
        activity_id=act_id,
        seq=seq_number,
        payload=act_payload,
        originator="user",
        create_time=act_time
    )
    db.add(db_act)

    # Update session updateTime
    session_payload = dict(s.payload)
    session_payload["updateTime"] = act_time
    s.payload = session_payload
    s.update_time = act_time

    await db.commit()

    return act_payload

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

    gh_repo = {
        "owner": s.owner,
        "repo": s.repo,
    }
    if s.default_branch:
        gh_repo["defaultBranch"] = {"displayName": s.default_branch}
    if s.branches:
        gh_repo["branches"] = [{"displayName": b} if isinstance(b, str) else b for b in s.branches]
    if s.is_private:
        gh_repo["isPrivate"] = True

    return {
        "name": s.name,
        "id": s.id,
        "githubRepo": gh_repo
    }

# SESSIONS ENDPOINTS
@router.post("/sessions")
async def create_session(
    request: Request,
    api_key: DBApiKey = Depends(verify_jules_api_key),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Creates and initiates an autonomous unattended Jules session.
    Returns immediately with the created session object and launches
    the execution engine in the background.
    """
    try:
        body = await request.json()
    except Exception:
        raise JulesAPIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="Invalid JSON request body.",
            gcp_status="INVALID_ARGUMENT"
        )

    prompt = body.get("prompt")
    if not prompt or not isinstance(prompt, str) or not prompt.strip():
        raise JulesAPIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="Field 'prompt' is required and must not be empty.",
            gcp_status="INVALID_ARGUMENT"
        )

    title = body.get("title") or f"Task: {prompt[:40]}..."
    source_context = body.get("sourceContext") or {}
    source_name = source_context.get("source") if isinstance(source_context, dict) else None

    from app.services.jules_engine import now_iso, jules_unattended_engine
    import uuid

    session_id = str(uuid.uuid4().hex[:16])
    now_ts = now_iso()

    session_payload = {
        "name": f"sessions/{session_id}",
        "id": session_id,
        "title": title,
        "prompt": prompt,
        "state": "QUEUED",
        "url": f"https://jules.google/sessions/{session_id}",
        "createTime": now_ts,
        "updateTime": now_ts,
        "sourceContext": source_context,
        "outputs": []
    }

    db_session = DBJulesSession(
        session_id=session_id,
        payload=session_payload,
        create_time=now_ts,
        update_time=now_ts,
        state="QUEUED",
        source=source_name,
        owner=api_key.owner
    )
    db.add(db_session)
    await db.commit()

    # Launch background unattended execution
    asyncio.create_task(
        jules_unattended_engine.execute_session_async(
            session_id=session_id,
            owner=api_key.owner,
            prompt=prompt,
            source=source_name,
            title=title
        )
    )

    return session_payload

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
