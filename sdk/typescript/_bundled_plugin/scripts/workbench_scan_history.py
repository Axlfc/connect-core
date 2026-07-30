import sqlite3
from workbench_db import WorkbenchDB

class WorkbenchScanHistory:
    def __init__(self, db_path=None):
        self.db = WorkbenchDB(db_path)

    def get_history_projections(self, workspace_id=None):
        conn = self.db._get_connection()
        try:
            cursor = conn.cursor()
            if workspace_id:
                cursor.execute(
                    "SELECT scan_id, status, cost_usd, created_at, completed_at FROM scans WHERE workspace_id = ? ORDER BY created_at DESC",
                    (workspace_id,)
                )
            else:
                cursor.execute(
                    "SELECT scan_id, status, cost_usd, created_at, completed_at FROM scans ORDER BY created_at DESC"
                )

            rows = cursor.fetchall()
            history = []
            for r in rows:
                history.append({
                    "scan_id": r[0],
                    "status": r[1],
                    "cost_usd": r[2],
                    "created_at": r[3],
                    "completed_at": r[4]
                })
            return history
        finally:
            conn.close()

    def has_been_scanned(self, workspace_path):
        conn = self.db._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT workspace_id FROM workspaces WHERE root_path = ?", (workspace_path,))
            row = cursor.fetchone()
            if not row:
                return False
            workspace_id = row[0]
            cursor.execute("SELECT COUNT(*) FROM scans WHERE workspace_id = ? AND status = 'complete'", (workspace_id,))
            count = cursor.fetchone()[0]
            return count > 0
        finally:
            conn.close()
