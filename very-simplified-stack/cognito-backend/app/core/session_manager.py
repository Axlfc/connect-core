import json
import uuid
import logging
import fcntl
import shutil
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class SessionMetadata(BaseModel):
    session_id: str
    cwd: str
    created_at: str
    updated_at: str
    message_count: int

class SessionManager:
    def __init__(self, sessions_dir: Optional[Path] = None):
        self.sessions_dir = sessions_dir or (Path.home() / ".cognito" / "sessions")
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.sessions_dir / "index.json"
        self.lock_path = self.sessions_dir / "index.json.lock"
        self._ensure_index()

    @contextmanager
    def _lock_index(self, shared: bool = False):
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
        with self._lock_index(shared=True):
            if not self.index_path.exists():
                return {}
            with open(self.index_path, "r") as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    return {}

    def _save_index(self, index: Dict[str, Dict[str, Any]]):
        temp_index_path = self.sessions_dir / f".index_{uuid.uuid4().hex}.tmp"
        with open(temp_index_path, "w") as f:
            json.dump(index, f, indent=2)
        temp_index_path.replace(self.index_path)

    def _mutate_index(self, update_fn: Callable[[Dict[str, Dict[str, Any]]], None]):
        with self._lock_index(shared=False):
            if not self.index_path.exists():
                index = {}
            else:
                with open(self.index_path, "r") as f:
                    try:
                        index = json.load(f)
                    except json.JSONDecodeError:
                        index = {}

            update_fn(index)
            self._save_index(index)

    def create(self, cwd: str) -> str:
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        # Create session file
        session_file = self.sessions_dir / f"{session_id}.jsonl"
        session_file.touch()

        resolved_cwd = str(Path(cwd).resolve())

        def _update(index: Dict[str, Dict[str, Any]]):
            index[session_id] = {
                "cwd": resolved_cwd,
                "created_at": now,
                "updated_at": now,
                "message_count": 0
            }

        self._mutate_index(_update)
        return session_id

    def open(self, session_id: str) -> SessionMetadata:
        index = self._get_index()
        if session_id not in index:
            raise FileNotFoundError(f"Session {session_id} not found")

        data = index[session_id]
        return SessionMetadata(session_id=session_id, **data)

    def fork_from(self, source_session_id: str, new_session_id: Optional[str] = None) -> str:
        source_meta = self.open(source_session_id)
        target_session_id = new_session_id or str(uuid.uuid4())

        source_file = self.sessions_dir / f"{source_session_id}.jsonl"
        target_file = self.sessions_dir / f"{target_session_id}.jsonl"

        # Copy file
        shutil.copy2(source_file, target_file)

        # Register in index
        now = datetime.now(timezone.utc).isoformat()

        def _update(index: Dict[str, Dict[str, Any]]):
            index[target_session_id] = {
                "cwd": source_meta.cwd,
                "created_at": now,
                "updated_at": now,
                "message_count": source_meta.message_count
            }

        self._mutate_index(_update)
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

        self._append_to_file(session_id, record)
        self._update_index_metrics(session_id, message_delta=1)

    def append_compaction(self, session_id: str, summary: str, covers_through_line: int) -> None:
        record = {
            "type": "compaction",
            "summary": summary,
            "covers_through_line": covers_through_line,
            "ts": datetime.now(timezone.utc).isoformat()
        }
        self._append_to_file(session_id, record)
        self._update_index_metrics(session_id)

    def _append_to_file(self, session_id: str, record: Dict[str, Any]):
        session_file = self.sessions_dir / f"{session_id}.jsonl"
        with open(session_file, "a") as f:
            self._lock_file(f)
            try:
                f.write(json.dumps(record) + "\n")
            finally:
                self._unlock_file(f)

    def _update_index_metrics(self, session_id: str, message_delta: int = 0):
        def _update(index: Dict[str, Dict[str, Any]]):
            if session_id in index:
                index[session_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
                index[session_id]["message_count"] += message_delta

        self._mutate_index(_update)

    def get_effective_messages(self, session_id: str, cwd: Optional[str] = None, include_system_prompt: bool = False) -> List[Dict[str, Any]]:
        session_file = self.sessions_dir / f"{session_id}.jsonl"
        if not session_file.exists():
            return []

        messages = []

        if include_system_prompt:
            resolved_cwd = cwd
            if not resolved_cwd:
                try:
                    meta = self.open(session_id)
                    resolved_cwd = meta.cwd
                except Exception:
                    resolved_cwd = None

            if resolved_cwd:
                try:
                    from app.core.system_prompt import build_system_message
                    system_prompt = build_system_message(resolved_cwd)
                    messages.append({"role": "system", "content": system_prompt})
                except Exception as e:
                    logger.warning(f"Failed to build system message for session {session_id} in {resolved_cwd}: {e}")

        compaction = None

        all_entries = []
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
            messages.append({"role": "system", "content": f"[Resumen de la conversación anterior]: {summary}"})
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

        session_file = self.sessions_dir / f"{session_id}.jsonl"
        index = self._get_index()

        if session_id not in index and not session_file.exists():
            raise FileNotFoundError(f"Session {session_id} not found")

        if not session_file.exists():
            raise FileNotFoundError(f"Session file for {session_id} not found")

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
        if total_turns == 0:
            return

        if num_turns >= total_turns:
            cutoff_index = user_turn_indices[0]
        else:
            keep_count = total_turns - num_turns
            cutoff_index = user_turn_indices[keep_count]

        kept_lines = lines[:cutoff_index]

        temp_file = self.sessions_dir / f".{session_id}_{uuid.uuid4().hex}.tmp"
        try:
            with open(temp_file, "w") as f:
                self._lock_file(f)
                try:
                    f.writelines(kept_lines)
                finally:
                    self._unlock_file(f)
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

        def _update(index: Dict[str, Dict[str, Any]]):
            if session_id in index:
                index[session_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
                index[session_id]["message_count"] = new_message_count

        self._mutate_index(_update)

    def archive_session(self, session_id: str) -> Path:
        session_file = self.sessions_dir / f"{session_id}.jsonl"
        index = self._get_index()

        if session_id not in index and not session_file.exists():
            raise FileNotFoundError(f"Session {session_id} not found")

        archive_dir = self.sessions_dir / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        target_path = archive_dir / f"{session_id}.jsonl"

        if session_file.exists():
            shutil.move(str(session_file), str(target_path))

        def _update(index: Dict[str, Dict[str, Any]]):
            if session_id in index:
                index.pop(session_id)

        self._mutate_index(_update)
        return target_path

    def delete_session(self, session_id: str) -> None:
        session_file = self.sessions_dir / f"{session_id}.jsonl"
        index = self._get_index()

        if session_id not in index and not session_file.exists():
            raise FileNotFoundError(f"Session {session_id} not found")

        if session_file.exists():
            session_file.unlink()

        def _update(index: Dict[str, Dict[str, Any]]):
            if session_id in index:
                index.pop(session_id)

        self._mutate_index(_update)
