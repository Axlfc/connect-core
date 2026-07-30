import sys
import os
import sqlite3
import uuid
import time
from workbench_schema import init_db

# Cross-platform file locking
try:
    import fcntl
except ImportError:
    fcntl = None

try:
    import msvcrt
except ImportError:
    msvcrt = None

class WorkbenchDB:
    def __init__(self, db_path=None):
        if not db_path:
            state_dir = os.getenv("CODEX_SECURITY_STATE_DIR") or os.getenv("CODEX_HOME") or os.path.expanduser("~/.codex")
            os.makedirs(state_dir, exist_ok=True)
            db_path = os.path.join(state_dir, "workbench.sqlite3")
        self.db_path = db_path
        init_db(self.db_path)

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def lock_db(self, f):
        if fcntl:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        elif msvcrt:
            # Simple windows lock
            pass

    def unlock_db(self, f):
        if fcntl:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        elif msvcrt:
            pass

    def start_scan(self, workspace_path):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            # 1. Ensure workspace exists
            workspace_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, workspace_path))
            cursor.execute(
                "INSERT OR IGNORE INTO workspaces (workspace_id, root_path) VALUES (?, ?)",
                (workspace_id, workspace_path)
            )

            # 2. Create scan
            scan_id = str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO scans (scan_id, workspace_id, status) VALUES (?, ?, ?)",
                (scan_id, workspace_id, "running")
            )
            conn.commit()
            return scan_id, workspace_id
        finally:
            conn.close()

    def complete_scan(self, scan_id, cost_usd=0.0):
        # Apply strict lock using lockfile to avoid race conditions
        lock_file_path = self.db_path + ".lock"
        with open(lock_file_path, "w") as f:
            self.lock_db(f)
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE scans SET status = ?, cost_usd = ?, completed_at = CURRENT_TIMESTAMP WHERE scan_id = ?",
                    ("complete", cost_usd, scan_id)
                )
                conn.commit()
            finally:
                conn.close()
                self.unlock_db(f)

    def fail_scan(self, scan_id):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE scans SET status = ?, completed_at = CURRENT_TIMESTAMP WHERE scan_id = ?",
                ("failed", scan_id)
            )
            conn.commit()
        finally:
            conn.close()

    def record_finding(self, workspace_id, cwe, file_path, line, severity, description):
        # Hash coordinates for unique fingerprint (preserves triage state across scans)
        fingerprint = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{cwe}:{file_path}:{line}"))
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO findings (fingerprint, workspace_id, cwe, file_path, line, severity, description)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(fingerprint) DO UPDATE SET
                    description = excluded.description,
                    severity = excluded.severity
                """,
                (fingerprint, workspace_id, cwe, file_path, line, severity, description)
            )
            conn.commit()
            return fingerprint
        finally:
            conn.close()

    def update_triage(self, fingerprint, triage_status):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE findings SET triage_status = ? WHERE fingerprint = ?",
                (triage_status, fingerprint)
            )
            conn.commit()
        finally:
            conn.close()

    def update_remediation(self, fingerprint, status, patch=None):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE findings SET remediation_status = ? WHERE fingerprint = ?",
                (status, fingerprint)
            )
            attempt_id = str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO finding_remediation_attempts (attempt_id, fingerprint, status, patch) VALUES (?, ?, ?, ?)",
                (attempt_id, fingerprint, status, patch)
            )
            conn.commit()
            return attempt_id
        finally:
            conn.close()
