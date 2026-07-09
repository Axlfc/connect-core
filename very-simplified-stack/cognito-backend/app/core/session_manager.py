import json
import uuid
import logging
import fcntl
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any
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
        self._ensure_index()

    def _ensure_index(self):
        if not self.index_path.exists():
            with open(self.index_path, "w") as f:
                json.dump({}, f)

    def _lock_file(self, f):
        fcntl.flock(f, fcntl.LOCK_EX)

    def _unlock_file(self, f):
        fcntl.flock(f, fcntl.LOCK_UN)

    def _get_index(self) -> Dict[str, Dict[str, Any]]:
        with open(self.index_path, "r") as f:
            self._lock_file(f)
            try:
                return json.load(f)
            finally:
                self._unlock_file(f)

    def _save_index(self, index: Dict[str, Dict[str, Any]]):
        with open(self.index_path, "w") as f:
            self._lock_file(f)
            try:
                json.dump(index, f, indent=2)
            finally:
                self._unlock_file(f)

    def create(self, cwd: str) -> str:
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        # Create session file
        session_file = self.sessions_dir / f"{session_id}.jsonl"
        session_file.touch()

        # Update index
        index = self._get_index()
        index[session_id] = {
            "cwd": str(Path(cwd).resolve()),
            "created_at": now,
            "updated_at": now,
            "message_count": 0
        }
        self._save_index(index)

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
        import shutil
        shutil.copy2(source_file, target_file)

        # Register in index
        now = datetime.now(timezone.utc).isoformat()
        index = self._get_index()
        index[target_session_id] = {
            "cwd": source_meta.cwd,
            "created_at": now,
            "updated_at": now,
            "message_count": source_meta.message_count
        }
        self._save_index(index)

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
        index = self._get_index()
        if session_id in index:
            index[session_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
            index[session_id]["message_count"] += message_delta
            self._save_index(index)

    def get_effective_messages(self, session_id: str) -> List[Dict[str, Any]]:
        session_file = self.sessions_dir / f"{session_id}.jsonl"
        if not session_file.exists():
            return []

        messages = []
        compaction = None
        compaction_line_index = -1

        all_entries = []
        with open(session_file, "r") as f:
            for i, line in enumerate(f):
                if not line.strip(): continue
                try:
                    data = json.loads(line)
                    all_entries.append((i, data))
                    if data.get("type") == "compaction":
                        compaction = data
                        compaction_line_index = i
                except json.JSONDecodeError:
                    logger.warning(f"Corrupt line {i} in session {session_id}")
                    continue

        if compaction:
            summary = compaction.get("summary", "")
            messages.append({"role": "system", "content": f"[Resumen de la conversación anterior]: {summary}"})
            start_line = compaction.get("covers_through_line", -1)

            for i, data in all_entries:
                if i > compaction_line_index: # Only messages after the compaction record itself
                     messages.append(self._to_ai_message(data))
                elif i > start_line and i < compaction_line_index:
                    # Actually, wait. Rule says: discard all messages anterior a covers_through_line.
                    # Covers through line might be the line INDEX in the file.
                    # If I have:
                    # 0: msg
                    # 1: msg
                    # 2: compaction {covers_through_line: 1}
                    # 3: msg
                    # Then effective messages are [System(summary), msg(3)]
                    pass # Handled by the logic below

            # Revised logic for get_effective_messages with compaction:
            messages = []
            messages.append({"role": "system", "content": f"[Resumen de la conversación anterior]: {compaction.get('summary', '')}"})
            for i, data in all_entries:
                if i > compaction_line_index and data.get("type") == "message":
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
