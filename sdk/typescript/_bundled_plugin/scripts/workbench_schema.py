import sqlite3

MIGRATIONS = [
    """
    CREATE TABLE IF NOT EXISTS workspaces (
        workspace_id TEXT PRIMARY KEY,
        root_path TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS scans (
        scan_id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL,
        status TEXT NOT NULL, -- 'running', 'complete', 'failed'
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP,
        cost_usd REAL DEFAULT 0.0,
        FOREIGN KEY(workspace_id) REFERENCES workspaces(workspace_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS findings (
        fingerprint TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL,
        cwe TEXT NOT NULL,
        file_path TEXT NOT NULL,
        line INTEGER NOT NULL,
        severity TEXT NOT NULL,
        description TEXT,
        triage_status TEXT DEFAULT 'pending', -- 'pending', 'false_positive', 'verified'
        remediation_status TEXT DEFAULT 'none', -- 'none', 'requested', 'applied', 'verified'
        FOREIGN KEY(workspace_id) REFERENCES workspaces(workspace_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS finding_remediation_attempts (
        attempt_id TEXT PRIMARY KEY,
        fingerprint TEXT NOT NULL,
        status TEXT NOT NULL, -- 'requested', 'applied', 'verified', 'failed'
        patch TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(fingerprint) REFERENCES findings(fingerprint)
    );
    """
]

def init_db(db_path):
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        for migration in MIGRATIONS:
            cursor.execute(migration)
        conn.commit()
    finally:
        conn.close()
