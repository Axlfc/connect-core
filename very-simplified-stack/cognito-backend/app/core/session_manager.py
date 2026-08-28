import os
import json
import uuid
import logging
import fcntl
import shutil
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
import anyio
from pydantic import BaseModel

from app.core.compaction import format_ledger_for_system_prompt
from app.core.database import get_db_sync_session

logger = logging.getLogger(__name__)

STORAGE_BACKEND = os.getenv("COGNITO_STORAGE_BACKEND", "local").lower()

class SessionMetadata(BaseModel):
    session_id: str
    cwd: str
    created_at: str
    updated_at: str
    message_count: int
    approval_timeout_seconds: Optional[int] = None
    blocked_actions_count: int = 0
    approval_summary: List[Dict[str, Any]] = []
    org_id: Optional[str] = None
    project_id: Optional[str] = None
    user_id: Optional[str] = None
    parent_session_id: Optional[str] = None
    branch_turn: Optional[int] = None

def is_postgres_backend() -> bool:
    return os.getenv("COGNITO_STORAGE_BACKEND", "local").lower() in ("postgres_redis", "postgres")

class SessionManager:
    """
    SessionManager manages agent session lifecycle and message history.
    Storage backend is selected via COGNITO_STORAGE_BACKEND env var:
      - 'local' (default): Uses local JSONL files and fcntl file locks.
      - 'postgres_redis' / 'postgres': Uses PostgreSQL for session/message persistence and Redis for distributed locks.
    """
    def __init__(self, sessions_dir: Optional[Path] = None):
        self.sessions_dir = sessions_dir or (Path.home() / ".cognito" / "sessions")
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.sessions_dir / "index.json"
        self.lock_path = self.sessions_dir / "index.json.lock"
        if not is_postgres_backend():
            self._ensure_index()

    @contextmanager
    def _lock_index(self, shared: bool = False):
        if is_postgres_backend():
            from app.core.redis_lock import distributed_lock
            with distributed_lock("index", lock_dir=self.sessions_dir):
                yield
        else:
            flags = fcntl.LOCK_SH if shared else fcntl.LOCK_EX
            lock_file = open(self.lock_path, "a+")
            try:
                fcntl.flock(lock_file.fileno(), flags)
                yield
            finally:
                try:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                except Exception:
                    pass
                lock_file.close()

    @contextmanager
    def _lock_session(self, session_id: str, shared: bool = False):
        if is_postgres_backend():
            from app.core.redis_lock import distributed_lock
            with distributed_lock(f"session:{session_id}", lock_dir=self.sessions_dir):
                yield
        else:
            session_lock_path = self.sessions_dir / f"{session_id}.lock"
            flags = fcntl.LOCK_SH if shared else fcntl.LOCK_EX
            lock_file = open(session_lock_path, "a+")
            try:
                fcntl.flock(lock_file.fileno(), flags)
                yield
            finally:
                try:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                except Exception:
                    pass
                lock_file.close()

    def _get_session_meta_path(self, session_id: str) -> Path:
        return self.sessions_dir / f"{session_id}.meta.json"

    def _read_session_meta(self, session_id: str) -> Optional[Dict[str, Any]]:
        if is_postgres_backend():
            from app.models.db import DBSession
            db = get_db_sync_session()
            try:
                row = db.query(DBSession).filter(DBSession.session_id == session_id).first()
                if row:
                    return {
                        "cwd": row.cwd,
                        "created_at": row.created_at,
                        "updated_at": row.updated_at,
                        "message_count": row.message_count,
                        "approval_timeout_seconds": row.approval_timeout_seconds,
                        "blocked_actions_count": row.blocked_actions_count,
                        "approval_summary": row.approval_summary or [],
                        "org_id": row.org_id,
                        "project_id": row.project_id,
                        "user_id": row.user_id,
                        "parent_session_id": row.parent_session_id,
                        "branch_turn": row.branch_turn,
                    }
                return None
            finally:
                db.close()

        meta_path = self._get_session_meta_path(session_id)
        if meta_path.exists():
            try:
                with open(meta_path, "r") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                pass

        if self.index_path.exists():
            try:
                with open(self.index_path, "r") as f:
                    idx = json.load(f)
                    session_file = self.sessions_dir / f"{session_id}.jsonl"
                    if session_id in idx and session_file.exists():
                        meta_data = idx[session_id]
                        self._write_session_meta(session_id, meta_data)
                        return meta_data
            except Exception:
                pass
        return None

    def _write_session_meta(self, session_id: str, data: Dict[str, Any]):
        if is_postgres_backend():
            from app.models.db import DBSession
            db = get_db_sync_session()
            try:
                row = db.query(DBSession).filter(DBSession.session_id == session_id).first()
                if not row:
                    row = DBSession(
                        session_id=session_id,
                        cwd=data["cwd"],
                        created_at=data["created_at"],
                        updated_at=data["updated_at"],
                        message_count=data.get("message_count", 0),
                        approval_timeout_seconds=data.get("approval_timeout_seconds"),
                        blocked_actions_count=data.get("blocked_actions_count", 0),
                        approval_summary=data.get("approval_summary", []),
                        org_id=data.get("org_id"),
                        project_id=data.get("project_id"),
                        user_id=data.get("user_id"),
                        parent_session_id=data.get("parent_session_id"),
                        branch_turn=data.get("branch_turn"),
                    )
                    db.add(row)
                else:
                    row.cwd = data["cwd"]
                    row.updated_at = data["updated_at"]
                    row.message_count = data.get("message_count", row.message_count)
                    row.approval_timeout_seconds = data.get("approval_timeout_seconds", row.approval_timeout_seconds)
                    row.blocked_actions_count = data.get("blocked_actions_count", row.blocked_actions_count)
                    row.approval_summary = data.get("approval_summary", row.approval_summary)
                    if data.get("org_id"): row.org_id = data["org_id"]
                    if data.get("project_id"): row.project_id = data["project_id"]
                    if data.get("user_id"): row.user_id = data["user_id"]
                    if data.get("parent_session_id"): row.parent_session_id = data["parent_session_id"]
                    if data.get("branch_turn") is not None: row.branch_turn = data["branch_turn"]
                db.commit()
                return
            finally:
                db.close()

        meta_path = self._get_session_meta_path(session_id)
        temp_meta_path = self.sessions_dir / f".meta_{session_id}_{uuid.uuid4().hex}.tmp"
        with open(temp_meta_path, "w") as f:
            json.dump(data, f)
        temp_meta_path.replace(meta_path)

    def _delete_session_meta(self, session_id: str):
        if is_postgres_backend():
            from app.models.db import DBSession, DBSessionMessage
            db = get_db_sync_session()
            try:
                db.query(DBSessionMessage).filter(DBSessionMessage.session_id == session_id).delete()
                db.query(DBSession).filter(DBSession.session_id == session_id).delete()
                db.commit()
                return
            finally:
                db.close()

        meta_path = self._get_session_meta_path(session_id)
        if meta_path.exists():
            meta_path.unlink()
        lock_file = self.sessions_dir / f"{session_id}.lock"
        if lock_file.exists():
            try:
                lock_file.unlink()
            except Exception:
                pass

    def _ensure_index(self):
        with self._lock_index(shared=False):
            if not self.index_path.exists():
                temp_index_path = self.sessions_dir / f".index_{uuid.uuid4().hex}.tmp"
                with open(temp_index_path, "w") as f:
                    json.dump({}, f)
                temp_index_path.replace(self.index_path)

    def _lock_file(self, f):
        fcntl.flock(f, fcntl.LOCK_EX)

    def _unlock_file(self, f):
        fcntl.flock(f, fcntl.LOCK_UN)

    def _get_index(self) -> Dict[str, Dict[str, Any]]:
        if is_postgres_backend():
            from app.models.db import DBSession
            db = get_db_sync_session()
            try:
                rows = db.query(DBSession).all()
                index = {}
                for row in rows:
                    index[row.session_id] = {
                        "cwd": row.cwd,
                        "created_at": row.created_at,
                        "updated_at": row.updated_at,
                        "message_count": row.message_count,
                        "approval_timeout_seconds": row.approval_timeout_seconds,
                        "blocked_actions_count": row.blocked_actions_count,
                        "approval_summary": row.approval_summary or [],
                        "org_id": row.org_id,
                        "project_id": row.project_id,
                        "user_id": row.user_id,
                        "parent_session_id": row.parent_session_id,
                        "branch_turn": row.branch_turn,
                    }
                return index
            finally:
                db.close()

        with self._lock_index(shared=False):
            index = {}
            for meta_file in self.sessions_dir.glob("*.meta.json"):
                sid = meta_file.name[:-10]
                try:
                    with open(meta_file, "r") as f:
                        index[sid] = json.load(f)
                except Exception:
                    pass

            if self.index_path.exists():
                try:
                    with open(self.index_path, "r") as f:
                        legacy_index = json.load(f)
                        for sid, data in legacy_index.items():
                            if sid not in index:
                                session_file = self.sessions_dir / f"{sid}.jsonl"
                                if session_file.exists():
                                    self._write_session_meta(sid, data)
                                    index[sid] = data
                except Exception:
                    pass

            self._save_index(index)
            return index

    def _save_index(self, index: Dict[str, Dict[str, Any]]):
        if is_postgres_backend():
            return
        temp_index_path = self.sessions_dir / f".index_{uuid.uuid4().hex}.tmp"
        with open(temp_index_path, "w") as f:
            json.dump(index, f, indent=2)
        temp_index_path.replace(self.index_path)

    def create(
        self,
        cwd: str,
        approval_timeout_seconds: Optional[int] = None,
        org_id: Optional[str] = None,
        project_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> str:
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        resolved_cwd = str(Path(cwd).resolve())

        meta_data = {
            "cwd": resolved_cwd,
            "created_at": now,
            "updated_at": now,
            "message_count": 0,
            "approval_timeout_seconds": approval_timeout_seconds,
            "blocked_actions_count": 0,
            "approval_summary": [],
            "org_id": org_id,
            "project_id": project_id,
            "user_id": user_id
        }

        # Create session file locally for compatibility
        session_file = self.sessions_dir / f"{session_id}.jsonl"
        session_file.touch()

        with self._lock_session(session_id, shared=False):
            self._write_session_meta(session_id, meta_data)

        if not is_postgres_backend():
            self._get_index()

        return session_id

    def open(self, session_id: str) -> SessionMetadata:
        with self._lock_session(session_id, shared=True):
            meta = self._read_session_meta(session_id)
            if not meta:
                raise FileNotFoundError(f"Session {session_id} not found")
            return SessionMetadata(
                session_id=session_id,
                cwd=meta["cwd"],
                created_at=meta["created_at"],
                updated_at=meta["updated_at"],
                message_count=meta.get("message_count", 0),
                approval_timeout_seconds=meta.get("approval_timeout_seconds"),
                blocked_actions_count=meta.get("blocked_actions_count", 0),
                approval_summary=meta.get("approval_summary", []),
                org_id=meta.get("org_id"),
                project_id=meta.get("project_id"),
                user_id=meta.get("user_id"),
                parent_session_id=meta.get("parent_session_id"),
                branch_turn=meta.get("branch_turn"),
            )

    def set_approval_timeout(self, session_id: str, timeout_seconds: int) -> bool:
        with self._lock_session(session_id, shared=False):
            meta = self._read_session_meta(session_id)
            if not meta:
                return False
            meta["approval_timeout_seconds"] = timeout_seconds
            meta["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._write_session_meta(session_id, meta)
        return True

    async def set_approval_timeout_async(self, session_id: str, timeout_seconds: int) -> bool:
        return await anyio.to_thread.run_sync(self.set_approval_timeout, session_id, timeout_seconds)

    def record_blocked_approval(self, session_id: str, decision_dict: Dict[str, Any]) -> None:
        with self._lock_session(session_id, shared=False):
            meta = self._read_session_meta(session_id)
            if meta:
                meta["blocked_actions_count"] = meta.get("blocked_actions_count", 0) + 1
                summary = meta.get("approval_summary", [])
                summary.append(decision_dict)
                meta["approval_summary"] = summary
                meta["updated_at"] = datetime.now(timezone.utc).isoformat()
                self._write_session_meta(session_id, meta)

    async def record_blocked_approval_async(self, session_id: str, decision_dict: Dict[str, Any]) -> None:
        await anyio.to_thread.run_sync(self.record_blocked_approval, session_id, decision_dict)

    async def open_async(self, session_id: str) -> SessionMetadata:
        return await anyio.to_thread.run_sync(self.open, session_id)

    async def append_message_async(
        self,
        session_id: str,
        role: str,
        content: str,
        tool_name: Optional[str] = None,
        tool_call_id: Optional[str] = None,
        tool_calls: Optional[List[Dict]] = None
    ) -> None:
        await anyio.to_thread.run_sync(
            self.append_message, session_id, role, content, tool_name, tool_call_id, tool_calls
        )

    async def get_effective_messages_async(
        self, session_id: str, cwd: Optional[str] = None, include_system_prompt: bool = False
    ) -> List[Dict[str, Any]]:
        return await anyio.to_thread.run_sync(
            self.get_effective_messages, session_id, cwd, include_system_prompt
        )

    def fork_from(self, source_session_id: str, new_session_id: Optional[str] = None, turn: Optional[int] = None) -> str:
        source_meta = self.open(source_session_id)
        target_session_id = new_session_id or str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        copied_msgs_count = 0
        branch_turn_val = turn

        if is_postgres_backend():
            from app.models.db import DBSessionMessage
            db = get_db_sync_session()
            try:
                source_msgs = db.query(DBSessionMessage).filter(DBSessionMessage.session_id == source_session_id).order_by(DBSessionMessage.seq.asc()).all()
                if turn is not None:
                    user_turn_seqs = [m.seq for m in source_msgs if m.type == "message" and m.role == "user"]
                    if turn <= 0:
                        source_msgs = []
                    elif turn <= len(user_turn_seqs):
                        cutoff_user_seq = user_turn_seqs[turn - 1]
                        next_user_seq = user_turn_seqs[turn] if turn < len(user_turn_seqs) else float('inf')
                        source_msgs = [m for m in source_msgs if m.seq < next_user_seq]

                for msg in source_msgs:
                    new_msg = DBSessionMessage(
                        message_id=str(uuid.uuid4()),
                        session_id=target_session_id,
                        seq=msg.seq,
                        type=msg.type,
                        role=msg.role,
                        content=msg.content,
                        tool_name=msg.tool_name,
                        tool_call_id=msg.tool_call_id,
                        tool_calls=msg.tool_calls,
                        summary=msg.summary,
                        covers_through_line=msg.covers_through_line,
                        context_ledger=msg.context_ledger,
                        delivered=msg.delivered,
                        steering_id=msg.steering_id,
                        ts=now,
                    )
                    db.add(new_msg)
                    if msg.type == "message":
                        copied_msgs_count += 1
                db.commit()
            finally:
                db.close()
        else:
            source_file = self.sessions_dir / f"{source_session_id}.jsonl"
            target_file = self.sessions_dir / f"{target_session_id}.jsonl"
            lines_to_copy = []

            with self._lock_session(source_session_id, shared=True):
                if source_file.exists():
                    with open(source_file, "r") as f:
                        lines = f.readlines()

                    if turn is not None:
                        user_turn_line_indices = []
                        for idx, line in enumerate(lines):
                            if not line.strip(): continue
                            try:
                                data = json.loads(line)
                                if isinstance(data, dict) and data.get("type") == "message" and data.get("role") == "user":
                                    user_turn_line_indices.append(idx)
                            except json.JSONDecodeError:
                                pass

                        if turn <= 0:
                            lines_to_copy = []
                        elif turn <= len(user_turn_line_indices):
                            cutoff_idx = user_turn_line_indices[turn] if turn < len(user_turn_line_indices) else len(lines)
                            lines_to_copy = lines[:cutoff_idx]
                        else:
                            lines_to_copy = lines
                    else:
                        lines_to_copy = lines

            with open(target_file, "w") as f:
                f.writelines(lines_to_copy)

            for line in lines_to_copy:
                if not line.strip(): continue
                try:
                    data = json.loads(line)
                    if isinstance(data, dict) and data.get("type") == "message":
                        copied_msgs_count += 1
                except json.JSONDecodeError:
                    pass

        meta_data = {
            "cwd": source_meta.cwd,
            "created_at": now,
            "updated_at": now,
            "message_count": copied_msgs_count,
            "org_id": source_meta.org_id,
            "project_id": source_meta.project_id,
            "user_id": source_meta.user_id,
            "parent_session_id": source_session_id,
            "branch_turn": branch_turn_val,
        }

        with self._lock_session(target_session_id, shared=False):
            self._write_session_meta(target_session_id, meta_data)

        if not is_postgres_backend():
            self._get_index()
        return target_session_id

    def continue_recent(self, cwd: str) -> Optional[str]:
        target_cwd = str(Path(cwd).resolve())
        index = self._get_index()

        sessions = [
            (sid, data) for sid, data in index.items()
            if data["cwd"] == target_cwd
        ]

        if not sessions:
            return None

        sessions.sort(key=lambda x: x[1]["updated_at"], reverse=True)
        return sessions[0][0]

    def list_all(self, cwd: Optional[str] = None) -> List[SessionMetadata]:
        target_cwd = str(Path(cwd).resolve()) if cwd else None
        index = self._get_index()

        results = []
        for sid, data in index.items():
            if target_cwd and data["cwd"] != target_cwd:
                continue
            results.append(SessionMetadata(session_id=sid, **data))

        return results

    def append_message(self, session_id: str, role: str, content: str, tool_name: Optional[str] = None, tool_call_id: Optional[str] = None, tool_calls: Optional[List[Dict]] = None) -> None:
        record = {
            "type": "message",
            "role": role,
            "content": content,
            "ts": datetime.now(timezone.utc).isoformat()
        }
        if tool_name: record["tool_name"] = tool_name
        if tool_call_id: record["tool_call_id"] = tool_call_id
        if tool_calls: record["tool_calls"] = tool_calls

        with self._lock_session(session_id, shared=False):
            if is_postgres_backend():
                from app.models.db import DBSessionMessage, DBSession
                from sqlalchemy import func
                db = get_db_sync_session()
                try:
                    max_seq = db.query(func.max(DBSessionMessage.seq)).filter(DBSessionMessage.session_id == session_id).scalar()
                    next_seq = (max_seq or 0) + 1
                    msg_row = DBSessionMessage(
                        message_id=str(uuid.uuid4()),
                        session_id=session_id,
                        seq=next_seq,
                        type="message",
                        role=role,
                        content=content,
                        tool_name=tool_name,
                        tool_call_id=tool_call_id,
                        tool_calls=tool_calls,
                        ts=record["ts"]
                    )
                    db.add(msg_row)
                    sess_row = db.query(DBSession).filter(DBSession.session_id == session_id).first()
                    if sess_row:
                        sess_row.updated_at = record["ts"]
                        sess_row.message_count += 1
                    db.commit()
                finally:
                    db.close()

            # Append to local file as well
            session_file = self.sessions_dir / f"{session_id}.jsonl"
            with open(session_file, "a") as f:
                f.write(json.dumps(record) + "\n")

            if not is_postgres_backend():
                meta = self._read_session_meta(session_id)
                if meta:
                    meta["updated_at"] = record["ts"]
                    meta["message_count"] = meta.get("message_count", 0) + 1
                    self._write_session_meta(session_id, meta)

    def append_compaction(
        self,
        session_id: str,
        summary: str,
        covers_through_line: int,
        context_ledger: Optional[Dict[str, Any]] = None
    ) -> None:
        record = {
            "type": "compaction",
            "summary": summary,
            "covers_through_line": covers_through_line,
            "ts": datetime.now(timezone.utc).isoformat()
        }
        if context_ledger is not None:
            record["context_ledger"] = context_ledger

        with self._lock_session(session_id, shared=False):
            if is_postgres_backend():
                from app.models.db import DBSessionMessage, DBSession
                from sqlalchemy import func
                db = get_db_sync_session()
                try:
                    max_seq = db.query(func.max(DBSessionMessage.seq)).filter(DBSessionMessage.session_id == session_id).scalar()
                    next_seq = (max_seq or 0) + 1
                    msg_row = DBSessionMessage(
                        message_id=str(uuid.uuid4()),
                        session_id=session_id,
                        seq=next_seq,
                        type="compaction",
                        summary=summary,
                        covers_through_line=covers_through_line,
                        context_ledger=context_ledger,
                        ts=record["ts"]
                    )
                    db.add(msg_row)
                    sess_row = db.query(DBSession).filter(DBSession.session_id == session_id).first()
                    if sess_row:
                        sess_row.updated_at = record["ts"]
                    db.commit()
                finally:
                    db.close()

            session_file = self.sessions_dir / f"{session_id}.jsonl"
            with open(session_file, "a") as f:
                f.write(json.dumps(record) + "\n")

            if not is_postgres_backend():
                meta = self._read_session_meta(session_id)
                if meta:
                    meta["updated_at"] = record["ts"]
                    self._write_session_meta(session_id, meta)

    def append_steering_message(self, session_id: str, content: str, steering_id: Optional[str] = None) -> str:
        sid = steering_id or f"steer-{uuid.uuid4().hex[:12]}"
        record = {
            "type": "steering",
            "id": sid,
            "content": content,
            "delivered": False,
            "ts": datetime.now(timezone.utc).isoformat()
        }
        with self._lock_session(session_id, shared=False):
            if is_postgres_backend():
                from app.models.db import DBSessionMessage, DBSession
                from sqlalchemy import func
                db = get_db_sync_session()
                try:
                    max_seq = db.query(func.max(DBSessionMessage.seq)).filter(DBSessionMessage.session_id == session_id).scalar()
                    next_seq = (max_seq or 0) + 1
                    msg_row = DBSessionMessage(
                        message_id=str(uuid.uuid4()),
                        session_id=session_id,
                        seq=next_seq,
                        type="steering",
                        steering_id=sid,
                        content=content,
                        delivered=False,
                        ts=record["ts"]
                    )
                    db.add(msg_row)
                    sess_row = db.query(DBSession).filter(DBSession.session_id == session_id).first()
                    if sess_row:
                        sess_row.updated_at = record["ts"]
                    db.commit()
                finally:
                    db.close()

            session_file = self.sessions_dir / f"{session_id}.jsonl"
            with open(session_file, "a") as f:
                f.write(json.dumps(record) + "\n")

            meta = self._read_session_meta(session_id)
            if meta:
                meta["updated_at"] = record["ts"]
                self._write_session_meta(session_id, meta)
        return sid

    async def append_steering_message_async(
        self, session_id: str, content: str, steering_id: Optional[str] = None
    ) -> str:
        return await anyio.to_thread.run_sync(
            self.append_steering_message, session_id, content, steering_id
        )

    def get_undelivered_steering_messages(self, session_id: str) -> List[Dict[str, Any]]:
        with self._lock_session(session_id, shared=True):
            if is_postgres_backend():
                from app.models.db import DBSessionMessage
                db = get_db_sync_session()
                try:
                    rows = db.query(DBSessionMessage).filter(
                        DBSessionMessage.session_id == session_id,
                        DBSessionMessage.type == "steering",
                        DBSessionMessage.delivered == False
                    ).order_by(DBSessionMessage.seq.asc()).all()
                    return [{"id": r.steering_id, "content": r.content, "ts": r.ts} for r in rows]
                finally:
                    db.close()

            session_file = self.sessions_dir / f"{session_id}.jsonl"
            if not session_file.exists():
                return []

            undelivered = []
            with open(session_file, "r") as f:
                for line in f:
                    line_str = line.strip()
                    if not line_str:
                        continue
                    try:
                        data = json.loads(line_str)
                        if (
                            isinstance(data, dict)
                            and data.get("type") == "steering"
                            and not data.get("delivered", False)
                        ):
                            undelivered.append({
                                "id": data.get("id"),
                                "content": data.get("content"),
                                "ts": data.get("ts")
                            })
                    except json.JSONDecodeError:
                        pass
            return undelivered

    async def get_undelivered_steering_messages_async(self, session_id: str) -> List[Dict[str, Any]]:
        return await anyio.to_thread.run_sync(self.get_undelivered_steering_messages, session_id)

    def mark_steering_delivered(
        self, session_id: str, steering_id: Optional[str] = None, content: Optional[str] = None
    ) -> bool:
        with self._lock_session(session_id, shared=False):
            if is_postgres_backend():
                from app.models.db import DBSessionMessage
                db = get_db_sync_session()
                try:
                    query = db.query(DBSessionMessage).filter(
                        DBSessionMessage.session_id == session_id,
                        DBSessionMessage.type == "steering",
                        DBSessionMessage.delivered == False
                    )
                    if steering_id:
                        query = query.filter(DBSessionMessage.steering_id == steering_id)
                    elif content:
                        query = query.filter(DBSessionMessage.content == content)

                    rows = query.all()
                    if rows:
                        for r in rows:
                            r.delivered = True
                        db.commit()
                        # Also update local file if exists
                        session_file = self.sessions_dir / f"{session_id}.jsonl"
                        if session_file.exists():
                            self._mark_steering_delivered_file(session_id, steering_id, content)
                        return True
                    return False
                finally:
                    db.close()

            return self._mark_steering_delivered_file(session_id, steering_id, content)

    def _mark_steering_delivered_file(
        self, session_id: str, steering_id: Optional[str] = None, content: Optional[str] = None
    ) -> bool:
        session_file = self.sessions_dir / f"{session_id}.jsonl"
        if not session_file.exists():
            return False

        updated = False
        lines = []

        with open(session_file, "r") as f:
            for line in f:
                line_str = line.strip()
                if not line_str:
                    lines.append(line)
                    continue
                try:
                    data = json.loads(line_str)
                    if (
                        isinstance(data, dict)
                        and data.get("type") == "steering"
                        and not data.get("delivered", False)
                    ):
                        match_id = steering_id and data.get("id") == steering_id
                        match_content = not steering_id and content and data.get("content") == content
                        if match_id or match_content:
                            data["delivered"] = True
                            updated = True
                            lines.append(json.dumps(data) + "\n")
                            continue
                except json.JSONDecodeError:
                    pass
                lines.append(line)

        if updated:
            temp_file = self.sessions_dir / f".{session_id}_{uuid.uuid4().hex}.tmp"
            try:
                with open(temp_file, "w") as f:
                    f.writelines(lines)
                temp_file.replace(session_file)
            except Exception:
                if temp_file.exists():
                    temp_file.unlink()
                raise

        return updated

    async def mark_steering_delivered_async(
        self, session_id: str, steering_id: Optional[str] = None, content: Optional[str] = None
    ) -> bool:
        return await anyio.to_thread.run_sync(
            self.mark_steering_delivered, session_id, steering_id, content
        )

    def get_effective_messages(self, session_id: str, cwd: Optional[str] = None, include_system_prompt: bool = False) -> List[Dict[str, Any]]:
        messages = []

        if include_system_prompt:
            resolved_cwd = cwd
            user_id = None
            project_id = None
            org_id = None
            try:
                meta = self.open(session_id)
                if not resolved_cwd:
                    resolved_cwd = meta.cwd
                user_id = meta.user_id
                project_id = meta.project_id
                org_id = meta.org_id
            except Exception:
                pass

            if resolved_cwd:
                try:
                    from app.core.system_prompt import build_system_message
                    system_prompt = build_system_message(
                        resolved_cwd,
                        user_id=user_id,
                        project_id=project_id,
                        org_id=org_id,
                    )
                    messages.append({"role": "system", "content": system_prompt})
                except Exception as e:
                    logger.warning(f"Failed to build system message for session {session_id} in {resolved_cwd}: {e}")

        all_entries = []
        compaction = None

        with self._lock_session(session_id, shared=True):
            if is_postgres_backend():
                from app.models.db import DBSessionMessage
                db = get_db_sync_session()
                try:
                    rows = db.query(DBSessionMessage).filter(DBSessionMessage.session_id == session_id).order_by(DBSessionMessage.seq.asc()).all()
                    for r in rows:
                        entry = {"type": r.type, "role": r.role, "content": r.content, "ts": r.ts}
                        if r.tool_name: entry["tool_name"] = r.tool_name
                        if r.tool_call_id: entry["tool_call_id"] = r.tool_call_id
                        if r.tool_calls: entry["tool_calls"] = r.tool_calls
                        if r.summary: entry["summary"] = r.summary
                        if r.covers_through_line is not None: entry["covers_through_line"] = r.covers_through_line
                        if r.context_ledger: entry["context_ledger"] = r.context_ledger
                        if r.steering_id: entry["id"] = r.steering_id
                        if r.delivered is not None: entry["delivered"] = r.delivered
                        all_entries.append((r.seq, entry))
                        if r.type == "compaction":
                            compaction = entry
                finally:
                    db.close()
            else:
                session_file = self.sessions_dir / f"{session_id}.jsonl"
                if not session_file.exists():
                    return messages

                with open(session_file, "r") as f:
                    for i, line in enumerate(f):
                        if not line.strip(): continue
                        try:
                            data = json.loads(line)
                            all_entries.append((i, data))
                            if data.get("type") == "compaction":
                                compaction = data
                        except json.JSONDecodeError:
                            logger.warning(f"Corrupt line {i} in session {session_id}")
                            continue

        if compaction:
            summary = compaction.get("summary", "")
            start_line = compaction.get("covers_through_line", -1)
            context_ledger = compaction.get("context_ledger")

            compaction_content = f"[Resumen de la conversación anterior]: {summary}"
            if context_ledger:
                ledger_text = format_ledger_for_system_prompt(context_ledger)
                if ledger_text:
                    compaction_content += f"\n\n{ledger_text}"

            summary_msg = {"role": "system", "content": compaction_content}
            if context_ledger:
                summary_msg["context_ledger"] = context_ledger
            messages.append(summary_msg)
            for i, data in all_entries:
                if i > start_line and data.get("type") == "message":
                    messages.append(self._to_ai_message(data))
            return messages
        else:
            for i, data in all_entries:
                if data.get("type") == "message":
                    messages.append(self._to_ai_message(data))
            return messages

    def _to_ai_message(self, data: Dict[str, Any]) -> Dict[str, Any]:
        msg = {"role": data["role"], "content": data["content"]}
        if "tool_name" in data: msg["name"] = data["tool_name"]
        if "tool_call_id" in data: msg["tool_call_id"] = data["tool_call_id"]
        if "tool_calls" in data: msg["tool_calls"] = data["tool_calls"]
        return msg

    def get_last_line_index(self, session_id: str) -> int:
        with self._lock_session(session_id, shared=True):
            if is_postgres_backend():
                from app.models.db import DBSessionMessage
                from sqlalchemy import func
                db = get_db_sync_session()
                try:
                    max_seq = db.query(func.max(DBSessionMessage.seq)).filter(DBSessionMessage.session_id == session_id).scalar()
                    return (max_seq or 0) - 1 if max_seq is not None else -1
                finally:
                    db.close()

            session_file = self.sessions_dir / f"{session_id}.jsonl"
            if not session_file.exists():
                return -1
            line_count = 0
            with open(session_file, "r") as f:
                for line in f:
                    if line.strip(): line_count += 1
            return line_count - 1

    def rollback_turns(self, session_id: str, num_turns: int) -> None:
        if num_turns <= 0:
            return

        with self._lock_session(session_id, shared=False):
            meta = self._read_session_meta(session_id)
            session_file = self.sessions_dir / f"{session_id}.jsonl"
            if not meta and not session_file.exists():
                raise FileNotFoundError(f"Session {session_id} not found")

            if is_postgres_backend():
                from app.models.db import DBSessionMessage, DBSession
                db = get_db_sync_session()
                try:
                    user_msgs = db.query(DBSessionMessage).filter(
                        DBSessionMessage.session_id == session_id,
                        DBSessionMessage.type == "message",
                        DBSessionMessage.role == "user"
                    ).order_by(DBSessionMessage.seq.asc()).all()

                    total_turns = len(user_msgs)
                    if total_turns == 0:
                        return

                    if num_turns >= total_turns:
                        cutoff_seq = user_msgs[0].seq
                    else:
                        keep_count = total_turns - num_turns
                        cutoff_seq = user_msgs[keep_count].seq

                    db.query(DBSessionMessage).filter(
                        DBSessionMessage.session_id == session_id,
                        DBSessionMessage.seq >= cutoff_seq
                    ).delete()

                    remaining_count = db.query(DBSessionMessage).filter(
                        DBSessionMessage.session_id == session_id,
                        DBSessionMessage.type == "message"
                    ).count()

                    sess = db.query(DBSession).filter(DBSession.session_id == session_id).first()
                    if sess:
                        sess.message_count = remaining_count
                        sess.updated_at = datetime.now(timezone.utc).isoformat()
                    db.commit()
                finally:
                    db.close()

            session_file = self.sessions_dir / f"{session_id}.jsonl"
            if session_file.exists():
                lines = []
                user_turn_indices = []
                with open(session_file, "r") as f:
                    for idx, line in enumerate(f):
                        lines.append(line)
                        line_str = line.strip()
                        if line_str:
                            try:
                                data = json.loads(line_str)
                                if isinstance(data, dict) and data.get("type") == "message" and data.get("role") == "user":
                                    user_turn_indices.append(idx)
                            except json.JSONDecodeError:
                                pass

                total_turns = len(user_turn_indices)
                if total_turns > 0:
                    cutoff_index = user_turn_indices[0] if num_turns >= total_turns else user_turn_indices[total_turns - num_turns]
                    kept_lines = lines[:cutoff_index]
                    temp_file = self.sessions_dir / f".{session_id}_{uuid.uuid4().hex}.tmp"
                    try:
                        with open(temp_file, "w") as f:
                            f.writelines(kept_lines)
                        temp_file.replace(session_file)
                    except Exception:
                        if temp_file.exists():
                            temp_file.unlink()
                        raise

                    new_message_count = 0
                    for line in kept_lines:
                        if line.strip():
                            try:
                                data = json.loads(line)
                                if isinstance(data, dict) and data.get("type") == "message":
                                    new_message_count += 1
                            except json.JSONDecodeError:
                                pass

                    meta = self._read_session_meta(session_id)
                    if meta:
                        meta["updated_at"] = datetime.now(timezone.utc).isoformat()
                        meta["message_count"] = new_message_count
                        self._write_session_meta(session_id, meta)

    def archive_session(self, session_id: str) -> Path:
        session_file = self.sessions_dir / f"{session_id}.jsonl"
        with self._lock_session(session_id, shared=False):
            meta = self._read_session_meta(session_id)
            if not meta and not session_file.exists():
                raise FileNotFoundError(f"Session {session_id} not found")

            archive_dir = self.sessions_dir / "archive"
            archive_dir.mkdir(parents=True, exist_ok=True)
            target_path = archive_dir / f"{session_id}.jsonl"

            if session_file.exists():
                shutil.move(str(session_file), str(target_path))

            self._delete_session_meta(session_id)

        if not is_postgres_backend():
            self._get_index()
        return target_path

    def purge_inactive_sessions(self, max_age_days: int) -> List[str]:
        if max_age_days < 0:
            return []

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=max_age_days)
        index = self._get_index()
        purged_ids: List[str] = []

        for sid, meta_data in list(index.items()):
            updated_at_str = meta_data.get("updated_at") or meta_data.get("created_at")
            is_expired = False
            if updated_at_str:
                try:
                    updated_at_dt = datetime.fromisoformat(updated_at_str)
                    if updated_at_dt.tzinfo is None:
                        updated_at_dt = updated_at_dt.replace(tzinfo=timezone.utc)
                    if updated_at_dt < cutoff:
                        is_expired = True
                except Exception as e:
                    logger.warning(f"Error parsing timestamp for session {sid}: {e}")
                    is_expired = False
            else:
                session_file = self.sessions_dir / f"{sid}.jsonl"
                if session_file.exists():
                    mtime = datetime.fromtimestamp(session_file.stat().st_mtime, tz=timezone.utc)
                    if mtime < cutoff:
                        is_expired = True

            if is_expired:
                try:
                    self.delete_session(sid)
                    purged_ids.append(sid)
                    logger.info(f"Purged inactive session {sid} (inactive > {max_age_days} days)")
                except Exception as e:
                    logger.error(f"Failed to purge session {sid}: {e}")

        return purged_ids

    async def purge_inactive_sessions_async(self, max_age_days: int) -> List[str]:
        return await anyio.to_thread.run_sync(self.purge_inactive_sessions, max_age_days)

    def delete_session(self, session_id: str) -> None:
        session_file = self.sessions_dir / f"{session_id}.jsonl"
        with self._lock_session(session_id, shared=False):
            meta = self._read_session_meta(session_id)
            if not meta and not session_file.exists():
                raise FileNotFoundError(f"Session {session_id} not found")

            if session_file.exists():
                session_file.unlink()

            self._delete_session_meta(session_id)

        if not is_postgres_backend():
            self._get_index()
