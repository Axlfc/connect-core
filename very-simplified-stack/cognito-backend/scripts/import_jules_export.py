#!/usr/bin/env python3
"""
CLI script to import a Jules session export directory into Postgres/SQLite.
Preserves original IDs and timestamps byte-for-byte with full idempotency.
Usage:
  python3 scripts/import_jules_export.py /path/to/export_dir --owner "user_1"
"""

import os
import sys
import json
import argparse
from pathlib import Path

# Add cognito-backend app to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import get_db_sync_session
from app.models.db import DBJulesSession, DBJulesActivity, DBSource

def import_export_dir_sync(export_dir: Path, owner: str) -> None:
    db = get_db_sync_session()

    export_path = Path(export_dir).resolve()
    if not export_path.exists():
        raise FileNotFoundError(f"Export directory '{export_path}' does not exist.")

    sessions_json_path = export_path / "sessions.json"
    sessions_data = []
    if sessions_json_path.exists():
        with open(sessions_json_path, "r", encoding="utf-8") as f:
            sessions_data = json.load(f)

    print(f"Importing export directory from '{export_path}' for owner '{owner}'...")

    imported_sessions_count = 0
    imported_activities_count = 0
    imported_sources_count = 0

    for s_dict in sessions_data:
        sid = str(s_dict.get("id"))

        # Look for detailed session.json and activities.json
        sess_dir = export_path / "sessions" / sid
        session_payload = s_dict
        if (sess_dir / "session.json").exists():
            with open(sess_dir / "session.json", "r", encoding="utf-8") as sf:
                session_payload = json.load(sf)

        create_time = str(session_payload.get("createTime", ""))
        update_time = str(session_payload.get("updateTime", ""))
        state = str(session_payload.get("state", "COMPLETED"))
        source = session_payload.get("sourceContext", {}).get("source", "")

        # Insert or update source
        if source and source.startswith("sources/github/"):
            parts = source.split("/")
            if len(parts) >= 4:
                src_owner = parts[2]
                src_repo = "/".join(parts[3:])
                existing_src = db.query(DBSource).filter(DBSource.name == source).first()
                if not existing_src:
                    src_obj = DBSource(
                        name=source,
                        id=f"{src_owner}-{src_repo}",
                        owner=src_owner,
                        repo=src_repo,
                        is_private=False,
                        default_branch="main",
                        branches=["main"]
                    )
                    db.add(src_obj)
                    imported_sources_count += 1

        # Upsert DBJulesSession idempotently
        existing_sess = db.query(DBJulesSession).filter(DBJulesSession.session_id == sid).first()
        if existing_sess:
            existing_sess.payload = session_payload
            existing_sess.create_time = create_time
            existing_sess.update_time = update_time
            existing_sess.state = state
            existing_sess.source = source
            existing_sess.owner = owner
        else:
            new_sess = DBJulesSession(
                session_id=sid,
                payload=session_payload,
                create_time=create_time,
                update_time=update_time,
                state=state,
                source=source,
                owner=owner
            )
            db.add(new_sess)
            imported_sessions_count += 1

        # Import activities
        act_file = sess_dir / "activities.json"
        if act_file.exists():
            with open(act_file, "r", encoding="utf-8") as af:
                activities_data = json.load(af)

            for idx, a_dict in enumerate(activities_data, start=1):
                aid = str(a_dict.get("id"))
                act_create_time = str(a_dict.get("createTime", ""))
                originator = str(a_dict.get("originator", "agent"))

                existing_act = db.query(DBJulesActivity).filter(
                    DBJulesActivity.session_id == sid,
                    DBJulesActivity.activity_id == aid
                ).first()

                if existing_act:
                    existing_act.seq = idx
                    existing_act.payload = a_dict
                    existing_act.originator = originator
                    existing_act.create_time = act_create_time
                else:
                    new_act = DBJulesActivity(
                        session_id=sid,
                        activity_id=aid,
                        seq=idx,
                        payload=a_dict,
                        originator=originator,
                        create_time=act_create_time
                    )
                    db.add(new_act)
                    imported_activities_count += 1

    db.commit()
    print(f"Import complete: {imported_sessions_count} sessions, {imported_activities_count} activities, {imported_sources_count} sources.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import Jules Export Directory")
    parser.add_argument("export_dir", type=str, help="Path to export directory")
    parser.add_argument("--owner", type=str, default="user_default", help="Owner ID / Org ID for imported sessions")
    args = parser.parse_args()

    import_export_dir_sync(Path(args.export_dir), args.owner)
