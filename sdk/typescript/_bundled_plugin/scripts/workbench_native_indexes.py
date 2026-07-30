import sqlite3
from workbench_db import WorkbenchDB

class WorkbenchNativeIndexes:
    def __init__(self, db_path=None):
        self.db = WorkbenchDB(db_path)

    def list_findings(self, workspace_id=None):
        conn = self.db._get_connection()
        try:
            cursor = conn.cursor()
            if workspace_id:
                cursor.execute("SELECT fingerprint, cwe, file_path, line, severity, triage_status, remediation_status FROM findings WHERE workspace_id = ? ORDER BY severity DESC", (workspace_id,))
            else:
                cursor.execute("SELECT fingerprint, cwe, file_path, line, severity, triage_status, remediation_status FROM findings ORDER BY severity DESC")

            rows = cursor.fetchall()
            findings = []
            for r in rows:
                findings.append({
                    "fingerprint": r[0],
                    "cwe": r[1],
                    "file_path": r[2],
                    "line": r[3],
                    "severity": r[4],
                    "triage_status": r[5],
                    "remediation_status": r[6]
                })
            return findings
        finally:
            conn.close()

    def list_workspaces(self):
        conn = self.db._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT workspace_id, root_path, created_at FROM workspaces ORDER BY created_at DESC")
            rows = cursor.fetchall()
            workspaces = []
            for r in rows:
                workspaces.append({
                    "workspace_id": r[0],
                    "root_path": r[1],
                    "created_at": r[2]
                })
            return workspaces
        finally:
            conn.close()
