#!/usr/bin/env python3
"""
CLI script to import Jules session export directories or ZIP files into Postgres/SQLite.
Supports multi-part archives (ZIP files and directories) without extracting ZIPs to disk.
Usage:
  python3 scripts/import_jules_export.py /path/to/part01.zip /path/to/index.zip --owner "user_1"
  python3 scripts/import_jules_export.py /path/to/export_dir --dry-run
"""

import os
import sys
import json
import zipfile
import argparse
from pathlib import Path
from typing import Dict, Any, List, Set, Tuple, Optional

# Add cognito-backend root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import get_db_sync_session
from app.models.db import DBJulesSession, DBJulesActivity, DBSource


def parse_source_entry(s_dict: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """
    Parses a sources.json entry into DBSource parameters.
    Returns (name, params) where name is 'sources/github/{owner}/{repo}'
    """
    verbatim_id = str(s_dict.get("id", ""))
    gh = s_dict.get("githubRepo", {}) or {}
    src_owner = str(gh.get("owner", ""))
    src_repo = str(gh.get("repo", ""))

    name = f"sources/github/{src_owner}/{src_repo}" if src_owner and src_repo else f"sources/{verbatim_id}"
    is_private = bool(gh.get("isPrivate", False))

    default_branch_obj = gh.get("defaultBranch", {}) or {}
    if isinstance(default_branch_obj, dict):
        default_branch = str(default_branch_obj.get("displayName", "main"))
    else:
        default_branch = str(default_branch_obj)

    raw_branches = gh.get("branches", []) or []
    branches = []
    for b in raw_branches:
        if isinstance(b, dict):
            branches.append(str(b.get("displayName", "")))
        else:
            branches.append(str(b))

    params = {
        "id": verbatim_id,
        "owner": src_owner,
        "repo": src_repo,
        "is_private": is_private,
        "default_branch": default_branch,
        "branches": branches,
    }
    return name, params


def read_content_from_inputs(paths: List[Path]) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, List[Any]], Dict[str, Any]]:
    """
    Scans input paths (zip files or directories) in memory without writing to disk.
    Returns:
      - sources_dict: {source_name: source_params}
      - sessions_summary: {session_id: session_dict}
      - detailed_sessions: {session_id: session_dict}
      - detailed_activities: {session_id: activities_list}
      - manifest_data: combined manifest dictionary
    """
    sources_dict: Dict[str, Any] = {}
    sessions_summary: Dict[str, Any] = {}
    detailed_sessions: Dict[str, Any] = {}
    detailed_activities: Dict[str, List[Any]] = {}
    manifest_data: Dict[str, Any] = {}

    for path_obj in paths:
        path_obj = path_obj.resolve()
        if not path_obj.exists():
            raise FileNotFoundError(f"Input path '{path_obj}' does not exist.")

        if path_obj.is_file() and (zipfile.is_zipfile(path_obj) or path_obj.suffix.lower() == ".zip"):
            with zipfile.ZipFile(path_obj, "r") as zf:
                for name in zf.namelist():
                    if name.endswith("/") or name.startswith("__MACOSX"):
                        continue
                    clean_name = name.split("/")

                    if "manifest.json" in clean_name[-1]:
                        try:
                            m = json.loads(zf.read(name).decode("utf-8"))
                            if isinstance(m, dict):
                                if "sessions_by_part" in m and isinstance(m["sessions_by_part"], dict):
                                    manifest_data.setdefault("sessions_by_part", {}).update(m["sessions_by_part"])
                                if "sessions" in m and isinstance(m["sessions"], list):
                                    manifest_data.setdefault("sessions", []).extend(m["sessions"])
                        except Exception as e:
                            print(f"[WARNING] Failed to parse {name} in {path_obj.name}: {e}")

                    elif clean_name[-1] == "sources.json":
                        try:
                            s_data = json.loads(zf.read(name).decode("utf-8"))
                            if isinstance(s_data, list):
                                for s_item in s_data:
                                    s_name, s_params = parse_source_entry(s_item)
                                    sources_dict[s_name] = s_params
                        except Exception as e:
                            print(f"[WARNING] Failed to parse {name} in {path_obj.name}: {e}")

                    elif clean_name[-1] == "sessions.json":
                        try:
                            sess_list = json.loads(zf.read(name).decode("utf-8"))
                            if isinstance(sess_list, list):
                                for s_item in sess_list:
                                    sid = str(s_item.get("id"))
                                    sessions_summary[sid] = s_item
                        except Exception as e:
                            print(f"[WARNING] Failed to parse {name} in {path_obj.name}: {e}")

                    elif "sessions" in clean_name:
                        idx = clean_name.index("sessions")
                        if len(clean_name) > idx + 2:
                            sid = clean_name[idx + 1]
                            fname = clean_name[idx + 2]
                            if fname == "session.json":
                                try:
                                    detailed_sessions[sid] = json.loads(zf.read(name).decode("utf-8"))
                                except Exception as e:
                                    print(f"[WARNING] Failed to parse {name} in {path_obj.name}: {e}")
                            elif fname == "activities.json":
                                try:
                                    detailed_activities[sid] = json.loads(zf.read(name).decode("utf-8"))
                                except Exception as e:
                                    print(f"[WARNING] Failed to parse {name} in {path_obj.name}: {e}")

        elif path_obj.is_dir():
            for root, _, files in os.walk(path_obj):
                for file_name in files:
                    file_path = Path(root) / file_name
                    rel_parts = file_path.relative_to(path_obj).parts

                    if file_name == "manifest.json":
                        try:
                            with open(file_path, "r", encoding="utf-8") as f:
                                m = json.load(f)
                                if isinstance(m, dict):
                                    if "sessions_by_part" in m and isinstance(m["sessions_by_part"], dict):
                                        manifest_data.setdefault("sessions_by_part", {}).update(m["sessions_by_part"])
                                    if "sessions" in m and isinstance(m["sessions"], list):
                                        manifest_data.setdefault("sessions", []).extend(m["sessions"])
                        except Exception as e:
                            print(f"[WARNING] Failed to parse {file_path}: {e}")

                    elif file_name == "sources.json":
                        try:
                            with open(file_path, "r", encoding="utf-8") as f:
                                s_data = json.load(f)
                                if isinstance(s_data, list):
                                    for s_item in s_data:
                                        s_name, s_params = parse_source_entry(s_item)
                                        sources_dict[s_name] = s_params
                        except Exception as e:
                            print(f"[WARNING] Failed to parse {file_path}: {e}")

                    elif file_name == "sessions.json":
                        try:
                            with open(file_path, "r", encoding="utf-8") as f:
                                sess_list = json.load(f)
                                if isinstance(sess_list, list):
                                    for s_item in sess_list:
                                        sid = str(s_item.get("id"))
                                        sessions_summary[sid] = s_item
                        except Exception as e:
                            print(f"[WARNING] Failed to parse {file_path}: {e}")

                    elif "sessions" in rel_parts:
                        idx = rel_parts.index("sessions")
                        if len(rel_parts) > idx + 2:
                            sid = rel_parts[idx + 1]
                            fname = rel_parts[idx + 2]
                            if fname == "session.json":
                                try:
                                    with open(file_path, "r", encoding="utf-8") as f:
                                        detailed_sessions[sid] = json.load(f)
                                except Exception as e:
                                    print(f"[WARNING] Failed to parse {file_path}: {e}")
                            elif fname == "activities.json":
                                try:
                                    with open(file_path, "r", encoding="utf-8") as f:
                                        detailed_activities[sid] = json.load(f)
                                except Exception as e:
                                    print(f"[WARNING] Failed to parse {file_path}: {e}")

    return sources_dict, sessions_summary, detailed_sessions, detailed_activities, manifest_data


def import_jules_export(
    input_paths: List[str],
    owner: str = "user_default",
    dry_run: bool = False
) -> int:
    """
    Imports Jules export data. Performs a transaction per session.
    Returns 0 on success, non-zero on error.
    """
    paths = [Path(p) for p in input_paths]
    sources_dict, sessions_summary, detailed_sessions, detailed_activities, manifest_data = read_content_from_inputs(paths)

    # Collect all session IDs to import
    all_session_ids = set(sessions_summary.keys()) | set(detailed_sessions.keys()) | set(detailed_activities.keys())

    # Manifest completeness check
    expected_sessions: Set[str] = set()
    if manifest_data:
        if "sessions_by_part" in manifest_data:
            for part_name, s_list in manifest_data["sessions_by_part"].items():
                if isinstance(s_list, list):
                    expected_sessions.update(str(s) for s in s_list)
        if "sessions" in manifest_data and isinstance(manifest_data["sessions"], list):
            expected_sessions.update(str(s) for s in manifest_data["sessions"])

    if expected_sessions:
        missing_sessions = sorted(expected_sessions - all_session_ids)
        if missing_sessions:
            print("=" * 70, file=sys.stderr)
            print("ERROR: MANIFEST COMPLETENESS CHECK FAILED", file=sys.stderr)
            print(f"Expected {len(expected_sessions)} sessions per manifest, but {len(missing_sessions)} were missing.", file=sys.stderr)
            print("Missing Session IDs:", file=sys.stderr)
            for sid in missing_sessions:
                print(f"  - {sid}", file=sys.stderr)
            print("=" * 70, file=sys.stderr)
            return 1

    imported_sources = 0
    updated_sources = 0
    skipped_sources = 0

    imported_sessions = 0
    updated_sessions = 0
    skipped_sessions = 0

    imported_activities = 0
    updated_activities = 0
    skipped_activities = 0

    # Process Sources
    if not dry_run:
        db = get_db_sync_session()
        try:
            for s_name, s_params in sources_dict.items():
                existing = db.query(DBSource).filter(DBSource.name == s_name).first()
                if existing:
                    existing.id = s_params["id"]
                    existing.owner = s_params["owner"]
                    existing.repo = s_params["repo"]
                    existing.is_private = s_params["is_private"]
                    existing.default_branch = s_params["default_branch"]
                    existing.branches = s_params["branches"]
                    updated_sources += 1
                else:
                    new_src = DBSource(
                        name=s_name,
                        id=s_params["id"],
                        owner=s_params["owner"],
                        repo=s_params["repo"],
                        is_private=s_params["is_private"],
                        default_branch=s_params["default_branch"],
                        branches=s_params["branches"]
                    )
                    db.add(new_src)
                    imported_sources += 1
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"[ERROR] Failed importing sources: {e}", file=sys.stderr)
        finally:
            db.close()
    else:
        imported_sources = len(sources_dict)

    # Process Sessions & Activities (Transaction per session)
    for sid in sorted(all_session_ids):
        session_payload = detailed_sessions.get(sid) or sessions_summary.get(sid) or {"id": sid}
        create_time = str(session_payload.get("createTime", ""))
        update_time = str(session_payload.get("updateTime", ""))
        state = str(session_payload.get("state", "COMPLETED"))
        source = session_payload.get("sourceContext", {}).get("source", "")

        if not dry_run:
            db = get_db_sync_session()
            try:
                # Fallback source creation if referenced source is missing
                if source and source.startswith("sources/github/"):
                    existing_src = db.query(DBSource).filter(DBSource.name == source).first()
                    if not existing_src:
                        parts = source.split("/")
                        if len(parts) >= 4:
                            src_owner = parts[2]
                            src_repo = "/".join(parts[3:])
                            print(f"[WARNING] Session '{sid}' references source '{source}' not found in sources.json. Creating fallback source.")
                            fallback_src = DBSource(
                                name=source,
                                id=f"{src_owner}-{src_repo}",
                                owner=src_owner,
                                repo=src_repo,
                                is_private=False,
                                default_branch="main",
                                branches=["main"]
                            )
                            db.add(fallback_src)
                            imported_sources += 1

                # Session upsert
                existing_sess = db.query(DBJulesSession).filter(DBJulesSession.session_id == sid).first()
                if existing_sess:
                    existing_sess.payload = session_payload
                    existing_sess.create_time = create_time
                    existing_sess.update_time = update_time
                    existing_sess.state = state
                    existing_sess.source = source
                    existing_sess.owner = owner
                    updated_sessions += 1
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
                    imported_sessions += 1

                # Activities upsert
                acts = detailed_activities.get(sid, [])
                for idx, a_dict in enumerate(acts, start=1):
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
                        updated_activities += 1
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
                        imported_activities += 1

                db.commit()
            except Exception as e:
                db.rollback()
                print(f"[ERROR] Failed to import session '{sid}': {e}", file=sys.stderr)
            finally:
                db.close()
        else:
            imported_sessions += 1
            imported_activities += len(detailed_activities.get(sid, []))

    # Print summary
    mode_str = " (DRY-RUN)" if dry_run else ""
    print("=" * 70)
    print(f"JULES EXPORT IMPORT SUMMARY{mode_str}")
    print("=" * 70)
    print(f"Sources:    {imported_sources} new, {updated_sources} updated, {skipped_sources} skipped")
    print(f"Sessions:   {imported_sessions} new, {updated_sessions} updated, {skipped_sessions} skipped")
    print(f"Activities: {imported_activities} new, {updated_activities} updated, {skipped_activities} skipped")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import Jules Session Export Archives or Directories")
    parser.add_argument("paths", nargs="+", type=str, help="Path(s) to export directory or ZIP archive files")
    parser.add_argument("--owner", type=str, default="user_default", help="Owner ID for imported sessions")
    parser.add_argument("--dry-run", action="store_true", help="Simulate import without writing to DB")

    args = parser.parse_args()
    ret_code = import_jules_export(args.paths, owner=args.owner, dry_run=args.dry_run)
    sys.exit(ret_code)
