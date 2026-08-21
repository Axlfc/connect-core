import hashlib
import re
import sqlite3
from typing import List, Optional, Set

DANGEROUS_PREFIXES_AND_PATTERNS = [
    r"rm\s+-rf",
    r"rm\s+-[^ ]*r[^ ]*f",
    r"curl\s+.*\|\s*(bash|sh)",
    r"wget\s+.*\|\s*(bash|sh)",
    r"\bsudo\b",
    r"python\s+-c",
    r"python3\s+-c",
    r"mkfs",
    r"dd\s+if=",
    r":\(\)\{\s*:\|\:&\s*\};:",  # fork bomb
    r"chmod\s+-R\s+777",
    r"chown\s+-R",
]

class ExecPolicy:
    """
    Engine for checking shell command risk policies.
    Identifies dangerous command patterns that force explicit human approval
    regardless of project trust settings.
    """
    def __init__(self, dangerous_patterns: Optional[List[str]] = None):
        self.dangerous_patterns = dangerous_patterns or DANGEROUS_PREFIXES_AND_PATTERNS

    def is_dangerous(self, command: str) -> bool:
        """
        Returns True if command contains any forbidden/dangerous prefix or pattern.
        """
        cmd_strip = command.strip()
        for pattern in self.dangerous_patterns:
            if re.search(pattern, cmd_strip, re.IGNORECASE):
                return True
        return False

    def requires_explicit_approval(self, command: str, project_trusted: bool = False) -> bool:
        """
        Determines whether execution of a command requires approval.
        Dangerous commands ALWAYS require explicit approval regardless of trust level.
        """
        if self.is_dangerous(command):
            return True
        return not project_trusted


class SessionApprovalCache:
    """
    In-memory or SQLite-backed approval cache for commands within a session.
    When a user approves a specific command in a session, its hash is stored.
    Subsequent executions of the same command in the same session can be auto-approved.
    """
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path
        self._in_memory_cache: dict[str, Set[str]] = {}
        if self.db_path:
            self._init_sqlite()

    def _init_sqlite(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS session_approvals (
                    session_id TEXT NOT NULL,
                    cmd_hash TEXT NOT NULL,
                    PRIMARY KEY (session_id, cmd_hash)
                )
                """
            )

    @staticmethod
    def hash_command(command: str) -> str:
        """
        Generates a SHA-256 hash for a normalized command string.
        """
        normalized = command.strip()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def approve(self, session_id: str, command: str) -> None:
        """
        Records user approval for a given command in a session.
        """
        cmd_hash = self.hash_command(command)
        if self.db_path:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO session_approvals (session_id, cmd_hash) VALUES (?, ?)",
                    (session_id, cmd_hash)
                )
        else:
            if session_id not in self._in_memory_cache:
                self._in_memory_cache[session_id] = set()
            self._in_memory_cache[session_id].add(cmd_hash)

    def is_approved(self, session_id: str, command: str) -> bool:
        """
        Checks if a command has been previously approved in the given session.
        """
        if not session_id:
            return False
        cmd_hash = self.hash_command(command)
        if self.db_path:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT 1 FROM session_approvals WHERE session_id = ? AND cmd_hash = ?",
                    (session_id, cmd_hash)
                )
                return cur.fetchone() is not None
        else:
            return cmd_hash in self._in_memory_cache.get(session_id, set())

    def clear_session(self, session_id: str) -> None:
        """
        Clears approved command hashes for a session.
        """
        if self.db_path:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM session_approvals WHERE session_id = ?", (session_id,))
        else:
            self._in_memory_cache.pop(session_id, None)


# Default global instances
default_exec_policy = ExecPolicy()
session_approval_cache = SessionApprovalCache()
