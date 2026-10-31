#!/usr/bin/env python3
"""
CLI script to export Jules sessions from Cognito Stack (PostgreSQL/SQLite)
into the canonical Google Jules Export format (ZIP archive or Directory).

Canonical layout:
  jules-export-YYYY-MM-DD/
    manifest.json
    sources.json
    sessions.json
    sessions/
      <session_id>/
        session.json
        activities.json

Usage:
  python3 scripts/export_jules_sessions.py --output /path/to/backup.zip --owner user_1
  python3 scripts/export_jules_sessions.py --output /path/to/backup_dir --format dir
"""

import os
import sys
import json
import zipfile
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add cognito-backend root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import get_db_sync_session
from app.models.db import DBJulesSession, DBJulesActivity, DBSource

def export_jules_sessions(
    output_path: str,
    owner: Optional[str] = None,
    output_format: str = "zip",
    session_ids: Optional[List[str]] = None
) -> int:
    out_p = Path(output_path).resolve()
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    top_dir = f"jules-export-{date_str}"

    print(f"📦 Exporting Jules sessions (owner={owner or 'ALL'}, format={output_format}) -> {out_p}")

    with get_db_sync_session() as db:
        # 1. Fetch Sources
        sources_rows = db.query(DBSource).all()
        sources_list = []
        for s in sources_rows:
            gh_repo = {
                "owner": s.owner,
                "repo": s.repo,
            }
            if s.default_branch:
                gh_repo["defaultBranch"] = {"displayName": s.default_branch}
            if s.branches:
                gh_repo["branches"] = [{"displayName": b} if isinstance(b, str) else b for b in s.branches]
            if s.is_private:
                gh_repo["isPrivate"] = True

            sources_list.append({
                "id": s.id,
                "githubRepo": gh_repo
            })

        # 2. Fetch Sessions
        sess_query = db.query(DBJulesSession)
        if owner:
            sess_query = sess_query.filter(DBJulesSession.owner == owner)
        if session_ids:
            sess_query = sess_query.filter(DBJulesSession.session_id.in_(session_ids))

        sessions_rows = sess_query.order_by(DBJulesSession.create_time.asc()).all()
        sessions_summary_list = []
        sessions_data = {}

        for s in sessions_rows:
            sid = s.session_id
            payload = dict(s.payload)
            sessions_summary_list.append(payload)

            # Fetch activities for this session
            act_rows = (
                db.query(DBJulesActivity)
                .filter(DBJulesActivity.session_id == sid)
                .order_by(DBJulesActivity.seq.asc(), DBJulesActivity.create_time.asc())
                .all()
            )
            act_list = [a.payload for a in act_rows]
            sessions_data[sid] = {
                "session": payload,
                "activities": act_list
            }

        # 3. Create Manifest
        manifest = {
            "version": "1.0",
            "exportDate": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "sessionCount": len(sessions_rows),
            "sourceCount": len(sources_list),
            "sessions": [s.session_id for s in sessions_rows]
        }

        # 4. Write Output
        if output_format == "zip":
            out_p.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(out_p, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.writestr(f"{top_dir}/manifest.json", json.dumps(manifest, indent=2))
                zf.writestr(f"{top_dir}/sources.json", json.dumps(sources_list, indent=2))
                zf.writestr(f"{top_dir}/sessions.json", json.dumps(sessions_summary_list, indent=2))

                for sid, data in sessions_data.items():
                    zf.writestr(f"{top_dir}/sessions/{sid}/session.json", json.dumps(data["session"], indent=2))
                    zf.writestr(f"{top_dir}/sessions/{sid}/activities.json", json.dumps(data["activities"], indent=2))

        else: # Directory export
            base_dir = out_p if out_p.name.startswith("jules-export-") else out_p / top_dir
            base_dir.mkdir(parents=True, exist_ok=True)

            (base_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            (base_dir / "sources.json").write_text(json.dumps(sources_list, indent=2), encoding="utf-8")
            (base_dir / "sessions.json").write_text(json.dumps(sessions_summary_list, indent=2), encoding="utf-8")

            sess_dir = base_dir / "sessions"
            sess_dir.mkdir(parents=True, exist_ok=True)

            for sid, data in sessions_data.items():
                s_folder = sess_dir / sid
                s_folder.mkdir(parents=True, exist_ok=True)
                (s_folder / "session.json").write_text(json.dumps(data["session"], indent=2), encoding="utf-8")
                (s_folder / "activities.json").write_text(json.dumps(data["activities"], indent=2), encoding="utf-8")

    print(f"✅ Export completed successfully: {len(sessions_rows)} sessions exported.")
    return 0

def main():
    parser = argparse.ArgumentParser(description="Export Jules Sessions to Canonical Format")
    parser.add_argument("--output", "-o", required=True, help="Output ZIP file path or destination directory")
    parser.add_argument("--owner", help="Filter by API key / Session owner")
    parser.add_argument("--format", choices=["zip", "dir"], default="zip", help="Export format (zip or dir)")
    parser.add_argument("--sessions", nargs="+", help="Specific session IDs to export")

    args = parser.parse_args()
    ret = export_jules_sessions(
        output_path=args.output,
        owner=args.owner,
        output_format=args.format,
        session_ids=args.sessions
    )
    sys.exit(ret)

if __name__ == "__main__":
    main()
