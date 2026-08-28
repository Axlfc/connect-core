#!/usr/bin/env python3
"""
Migration Script: Local Session Data (JSONL/SQLite) -> PostgreSQL (AUD-012/AUD-032)

Usage:
    python3 scripts/migrate_sessions_local_to_postgres.py [--sessions-dir /path/to/sessions]

Description:
    Scans local session files (.meta.json, .jsonl, index.json) and copies
    all session metadata and message history into the PostgreSQL database schema
    without loss of history.
"""

import os
import sys
import json
import uuid
import argparse
import logging
from pathlib import Path
from datetime import datetime, timezone

# Add backend app directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from app.core.database import DATABASE_URL, run_migrations
from app.models.db import DBSession, DBSessionMessage

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("cognito.migration")

from app.core.database import get_db_sync_session as get_sync_db_session

def migrate_sessions(sessions_dir: Path) -> dict:
    if not sessions_dir.exists():
        logger.warning(f"Sessions directory {sessions_dir} does not exist. Nothing to migrate.")
        return {"sessions_migrated": 0, "messages_migrated": 0}

    logger.info(f"Starting session data migration from {sessions_dir} to PostgreSQL...")
    db = get_sync_db_session()

    sessions_migrated = 0
    messages_migrated = 0

    try:
        # Step 1: Collect session IDs and metadata
        meta_files = list(sessions_dir.glob("*.meta.json"))
        session_metas = {}

        for meta_file in meta_files:
            sid = meta_file.name[:-10]
            try:
                with open(meta_file, "r") as f:
                    session_metas[sid] = json.load(f)
            except Exception as e:
                logger.error(f"Failed reading meta file {meta_file}: {e}")

        # Fallback to index.json for any un-migrated meta
        index_file = sessions_dir / "index.json"
        if index_file.exists():
            try:
                with open(index_file, "r") as f:
                    idx = json.load(f)
                    for sid, meta_data in idx.items():
                        if sid not in session_metas:
                            session_metas[sid] = meta_data
            except Exception as e:
                logger.warning(f"Error reading index.json: {e}")

        # Scan for any orphan .jsonl files without meta
        for jsonl_file in sessions_dir.glob("*.jsonl"):
            sid = jsonl_file.stem
            if sid not in session_metas:
                session_metas[sid] = {
                    "cwd": str(Path.cwd()),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "message_count": 0,
                    "org_id": "org-legacy-migrated",
                    "user_id": "usr-legacy-admin"
                }

        # Step 2: Perform migration into PostgreSQL
        for sid, meta in session_metas.items():
            # Check or create DBSession
            existing_sess = db.query(DBSession).filter(DBSession.session_id == sid).first()
            if not existing_sess:
                existing_sess = DBSession(
                    session_id=sid,
                    cwd=meta.get("cwd", str(Path.cwd())),
                    created_at=meta.get("created_at", datetime.now(timezone.utc).isoformat()),
                    updated_at=meta.get("updated_at", datetime.now(timezone.utc).isoformat()),
                    message_count=meta.get("message_count", 0),
                    approval_timeout_seconds=meta.get("approval_timeout_seconds"),
                    blocked_actions_count=meta.get("blocked_actions_count", 0),
                    approval_summary=meta.get("approval_summary", []),
                    org_id=meta.get("org_id", "org-legacy-migrated"),
                    project_id=meta.get("project_id"),
                    user_id=meta.get("user_id", "usr-legacy-admin"),
                )
                db.add(existing_sess)
                db.commit()
                sessions_migrated += 1

            # Migrate JSONL message history
            jsonl_file = sessions_dir / f"{sid}.jsonl"
            if jsonl_file.exists():
                existing_msg_count = db.query(DBSessionMessage).filter(DBSessionMessage.session_id == sid).count()
                max_seq = db.query(func.max(DBSessionMessage.seq)).filter(DBSessionMessage.session_id == sid).scalar() or 0

                lines_to_migrate = []
                with open(jsonl_file, "r") as f:
                    for line in f:
                        line_str = line.strip()
                        if line_str:
                            try:
                                lines_to_migrate.append(json.loads(line_str))
                            except json.JSONDecodeError:
                                pass

                # If missing messages, insert remaining lines starting from next seq
                if len(lines_to_migrate) > existing_msg_count:
                    for idx, data in enumerate(lines_to_migrate[existing_msg_count:], start=existing_msg_count + 1):
                        msg_row = DBSessionMessage(
                            message_id=str(uuid.uuid4()),
                            session_id=sid,
                            seq=idx,
                            type=data.get("type", "message"),
                            role=data.get("role"),
                            content=data.get("content"),
                            tool_name=data.get("tool_name"),
                            tool_call_id=data.get("tool_call_id"),
                            tool_calls=data.get("tool_calls"),
                            summary=data.get("summary"),
                            covers_through_line=data.get("covers_through_line"),
                            context_ledger=data.get("context_ledger"),
                            delivered=data.get("delivered", False),
                            steering_id=data.get("id"),
                            ts=data.get("ts", datetime.now(timezone.utc).isoformat())
                        )
                        db.add(msg_row)
                        messages_migrated += 1

                    existing_sess.message_count = len(lines_to_migrate)
                    db.commit()

        logger.info(f"Migration finished successfully: {sessions_migrated} sessions, {messages_migrated} messages migrated.")
        return {"sessions_migrated": sessions_migrated, "messages_migrated": messages_migrated}
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def main():
    parser = argparse.ArgumentParser(description="Migrate local Cognito session data to PostgreSQL")
    parser.add_argument("--sessions-dir", type=str, help="Path to local sessions directory")
    args = parser.parse_args()

    sessions_dir_path = Path(args.sessions_dir) if args.sessions_dir else (Path.home() / ".cognito" / "sessions")
    migrate_sessions(sessions_dir_path)

if __name__ == "__main__":
    main()
