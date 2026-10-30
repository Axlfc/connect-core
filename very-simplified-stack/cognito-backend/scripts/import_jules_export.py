#!/usr/bin/env python3
"""
CLI script to import Jules session export directories or ZIP files into Postgres/SQLite.
Supports multi-part archives (ZIP files and directories) without extracting ZIPs to disk.
Usage:
  python3 scripts/import_jules_export.py /path/to/part01.zip /path/to/index.zip --owner "user_1"
  python3 scripts/import_jules_export.py /path/to/export_dir --owner "user_1" --dry-run
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

    default_branch_obj = gh.get("defaultBranch")
    if default_branch_obj is None:
        default_branch = ""
    elif isinstance(default_branch_obj, dict):
        default_branch = str(default_branch_obj.get("displayName", ""))
    else:
        default_branch = str(default_branch_obj)

    raw_branches = gh.get("branches")
    if raw_branches is None:
        branches = []
    else:
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


def build_index_and_metadata(paths: List[Path]) -> Tuple[
    Dict[str, Any],
    Dict[str, Any],
    Dict[str, Any],
    Dict[str, Dict[str, Tuple[str, Any]]],
    List[Tuple[str, str, str]],
    bool
]:
    """
    Scans input paths (ZIP files or directories) without loading session contents into memory.
    Returns:
      - sources_dict: {source_name: source_params}
      - sessions_summary: {session_id: session_dict}
      - manifest_data: combined manifest dictionary
      - index: {session_id: {"session": (type, loc), "activities": (type, loc)}}
      - session_conflicts: [(session_id, first_loc, ignored_loc)]
      - found_reference: True if sessions.json or manifest.json file was found
    """
    sources_dict: Dict[str, Any] = {}
    sessions_summary: Dict[str, Any] = {}
    manifest_data: Dict[str, Any] = {}
    index: Dict[str, Dict[str, Tuple[str, Any]]] = {}
    session_conflicts: List[Tuple[str, str, str]] = []
    found_reference = False

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
                        found_reference = True
                        try:
                            m = json.loads(zf.read(name).decode("utf-8"))
                            if isinstance(m, dict):
                                if "sessions_by_part" in m and isinstance(m["sessions_by_part"], dict):
                                    manifest_data.setdefault("sessions_by_part", {}).update(m["sessions_by_part"])
                                if "sessions" in m and isinstance(m["sessions"], list):
                                    manifest_data.setdefault("sessions", []).extend(m["sessions"])
                        except Exception as e:
                            print(f"[WARNING] Failed to parse {name} in {path_obj.name}: {e}", file=sys.stderr)

                    elif clean_name[-1] == "sources.json":
                        try:
                            s_data = json.loads(zf.read(name).decode("utf-8"))
                            if isinstance(s_data, list):
                                for s_item in s_data:
                                    s_name, s_params = parse_source_entry(s_item)
                                    sources_dict[s_name] = s_params
                        except Exception as e:
                            print(f"[WARNING] Failed to parse {name} in {path_obj.name}: {e}", file=sys.stderr)

                    elif clean_name[-1] == "sessions.json":
                        found_reference = True
                        try:
                            sess_list = json.loads(zf.read(name).decode("utf-8"))
                            if isinstance(sess_list, list):
                                for s_item in sess_list:
                                    sid = str(s_item.get("id"))
                                    sessions_summary[sid] = s_item
                        except Exception as e:
                            print(f"[WARNING] Failed to parse {name} in {path_obj.name}: {e}", file=sys.stderr)

                    elif "sessions" in clean_name:
                        idx = clean_name.index("sessions")
                        if len(clean_name) > idx + 2:
                            sid = clean_name[idx + 1]
                            fname = clean_name[idx + 2]
                            loc = (path_obj, name)
                            sess_entry = index.setdefault(sid, {})
                            if fname == "session.json":
                                if "session" in sess_entry:
                                    first_loc = str(sess_entry["session"][1])
                                    session_conflicts.append((sid, first_loc, str(name)))
                                else:
                                    sess_entry["session"] = ("zip", loc)
                            elif fname == "activities.json":
                                if "activities" in sess_entry:
                                    first_loc = str(sess_entry["activities"][1])
                                    session_conflicts.append((sid, first_loc, str(name)))
                                else:
                                    sess_entry["activities"] = ("zip", loc)

        elif path_obj.is_dir():
            for root, _, files in os.walk(path_obj):
                for file_name in files:
                    file_path = Path(root) / file_name
                    rel_parts = file_path.relative_to(path_obj).parts

                    if file_name == "manifest.json":
                        found_reference = True
                        try:
                            with open(file_path, "r", encoding="utf-8") as f:
                                m = json.load(f)
                                if isinstance(m, dict):
                                    if "sessions_by_part" in m and isinstance(m["sessions_by_part"], dict):
                                        manifest_data.setdefault("sessions_by_part", {}).update(m["sessions_by_part"])
                                    if "sessions" in m and isinstance(m["sessions"], list):
                                        manifest_data.setdefault("sessions", []).extend(m["sessions"])
                        except Exception as e:
                            print(f"[WARNING] Failed to parse {file_path}: {e}", file=sys.stderr)

                    elif file_name == "sources.json":
                        try:
                            with open(file_path, "r", encoding="utf-8") as f:
                                s_data = json.load(f)
                                if isinstance(s_data, list):
                                    for s_item in s_data:
                                        s_name, s_params = parse_source_entry(s_item)
                                        sources_dict[s_name] = s_params
                        except Exception as e:
                            print(f"[WARNING] Failed to parse {file_path}: {e}", file=sys.stderr)

                    elif file_name == "sessions.json":
                        found_reference = True
                        try:
                            with open(file_path, "r", encoding="utf-8") as f:
                                sess_list = json.load(f)
                                if isinstance(sess_list, list):
                                    for s_item in sess_list:
                                        sid = str(s_item.get("id"))
                                        sessions_summary[sid] = s_item
                        except Exception as e:
                            print(f"[WARNING] Failed to parse {file_path}: {e}", file=sys.stderr)

                    elif "sessions" in rel_parts:
                        idx = rel_parts.index("sessions")
                        if len(rel_parts) > idx + 2:
                            sid = rel_parts[idx + 1]
                            fname = rel_parts[idx + 2]
                            sess_entry = index.setdefault(sid, {})
                            if fname == "session.json":
                                if "session" in sess_entry:
                                    first_loc = str(sess_entry["session"][1])
                                    session_conflicts.append((sid, first_loc, str(file_path)))
                                else:
                                    sess_entry["session"] = ("dir", file_path)
                            elif fname == "activities.json":
                                if "activities" in sess_entry:
                                    first_loc = str(sess_entry["activities"][1])
                                    session_conflicts.append((sid, first_loc, str(file_path)))
                                else:
                                    sess_entry["activities"] = ("dir", file_path)

    return sources_dict, sessions_summary, manifest_data, index, session_conflicts, found_reference


def read_single_session_data(session_info: Dict[str, Tuple[str, Any]]) -> Tuple[Optional[Dict[str, Any]], Optional[List[Any]]]:
    """
    Loads session.json and activities.json for a single session on demand from the index info.
    """
    sess_data = None
    act_data = None

    if "session" in session_info:
        src_type, loc = session_info["session"]
        if src_type == "zip":
            zip_path, member = loc
            with zipfile.ZipFile(zip_path, "r") as zf:
                sess_data = json.loads(zf.read(member).decode("utf-8"))
        elif src_type == "dir":
            with open(loc, "r", encoding="utf-8") as f:
                sess_data = json.load(f)

    if "activities" in session_info:
        src_type, loc = session_info["activities"]
        if src_type == "zip":
            zip_path, member = loc
            with zipfile.ZipFile(zip_path, "r") as zf:
                act_data = json.loads(zf.read(member).decode("utf-8"))
        elif src_type == "dir":
            with open(loc, "r", encoding="utf-8") as f:
                act_data = json.load(f)

    return sess_data, act_data


def import_jules_export(
    input_paths: List[str],
    owner: str,
    dry_run: bool = False,
    allow_partial: bool = False
) -> int:
    """
    Imports Jules export data. Performs a transaction per session.
    Returns:
      0: Complete success
      1: Import/DB runtime errors occurred
      2: Completeness check failed without --allow-partial
      3: Partial import completed with --allow-partial
    """
    paths = [Path(p) for p in input_paths]
    sources_dict, sessions_summary, manifest_data, index, session_conflicts, found_reference = build_index_and_metadata(paths)

    # Calculate expected sessions
    expected_sessions: Set[str] = set(sessions_summary.keys())
    if manifest_data:
        if "sessions_by_part" in manifest_data and isinstance(manifest_data["sessions_by_part"], dict):
            for part_name, s_list in manifest_data["sessions_by_part"].items():
                if isinstance(s_list, list):
                    expected_sessions.update(str(s) for s in s_list)
        if "sessions" in manifest_data and isinstance(manifest_data["sessions"], list):
            expected_sessions.update(str(s) for s in manifest_data["sessions"])

    # Present sessions must have BOTH session.json and activities.json
    present_sessions: Set[str] = {
        sid for sid, data in index.items()
        if "session" in data and "activities" in data
    }

    has_completeness_reference = found_reference
    partial_import_occurred = False

    if not has_completeness_reference:
        print("=" * 70, file=sys.stderr)
        print("ERROR: COMPLETENESS CHECK FAILED - NO SESSIONS.JSON OR MANIFEST.JSON FOUND", file=sys.stderr)
        print("There is no completeness reference available in the provided inputs.", file=sys.stderr)
        if not allow_partial:
            print("Use --allow-partial to allow importing present sessions without a completeness reference.", file=sys.stderr)
            print("=" * 70, file=sys.stderr)
            return 2
        print("Proceeding with partial import due to --allow-partial.", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        partial_import_occurred = True
    else:
        missing_sessions = sorted(expected_sessions - present_sessions)
        if missing_sessions:
            print("=" * 70, file=sys.stderr)
            print("ERROR: MANIFEST COMPLETENESS CHECK FAILED", file=sys.stderr)
            print(f"Expected {len(expected_sessions)} sessions per reference, but {len(missing_sessions)} were missing both session.json and activities.json.", file=sys.stderr)
            print("Missing Session IDs:", file=sys.stderr)
            for sid in missing_sessions:
                print(f"  - {sid}", file=sys.stderr)
            if not allow_partial:
                print("Aborting import without writing to database. Use --allow-partial to import present sessions.", file=sys.stderr)
                print("=" * 70, file=sys.stderr)
                return 2
            print("Proceeding with partial import due to --allow-partial.", file=sys.stderr)
            print("=" * 70, file=sys.stderr)
            partial_import_occurred = True

    imported_sources = 0
    updated_sources = 0
    failed_sources: List[Tuple[str, str]] = []

    imported_sessions = 0
    updated_sessions = 0
    failed_sessions: List[Tuple[str, str]] = []

    imported_activities = 0
    updated_activities = 0

    duplicates_discarded: List[Tuple[str, str]] = []
    fallback_sources: List[str] = []

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
            failed_sources.append(("sources.json", str(e)))
            imported_sources = 0
            updated_sources = 0
        finally:
            db.close()
    else:
        imported_sources = len(sources_dict)

    # Process Sessions & Activities (Transaction per session)
    for sid in sorted(present_sessions):
        sess_payload, acts_raw = read_single_session_data(index[sid])
        if sess_payload is None:
            sess_payload = sessions_summary.get(sid) or {"id": sid}

        create_time = str(sess_payload.get("createTime", ""))
        update_time = str(sess_payload.get("updateTime", ""))
        state = str(sess_payload.get("state", "COMPLETED"))
        source = sess_payload.get("sourceContext", {}).get("source", "")

        # Activity deduplication
        unique_acts: List[Dict[str, Any]] = []
        seen_aids: Set[str] = set()
        for a_dict in (acts_raw or []):
            aid = str(a_dict.get("id"))
            if aid in seen_aids:
                duplicates_discarded.append((sid, aid))
            else:
                seen_aids.add(aid)
                unique_acts.append(a_dict)

        if not dry_run:
            db = get_db_sync_session()
            try:
                # Fallback source creation if referenced source is missing
                if source and source.startswith("sources/github/"):
                    existing_src = db.query(DBSource).filter(DBSource.name == source).first()
                    if not existing_src and source not in sources_dict:
                        parts = source.split("/")
                        if len(parts) >= 4:
                            src_owner = parts[2]
                            src_repo = "/".join(parts[3:])
                            fallback_src = DBSource(
                                name=source,
                                id=f"{src_owner}-{src_repo}",
                                owner=src_owner,
                                repo=src_repo,
                                is_private=False,
                                default_branch="",
                                branches=[]
                            )
                            db.add(fallback_src)
                            fallback_sources.append(source)

                # Session upsert
                existing_sess = db.query(DBJulesSession).filter(DBJulesSession.session_id == sid).first()
                is_session_update = bool(existing_sess)
                if existing_sess:
                    existing_sess.payload = sess_payload
                    existing_sess.create_time = create_time
                    existing_sess.update_time = update_time
                    existing_sess.state = state
                    existing_sess.source = source
                    existing_sess.owner = owner
                else:
                    new_sess = DBJulesSession(
                        session_id=sid,
                        payload=sess_payload,
                        create_time=create_time,
                        update_time=update_time,
                        state=state,
                        source=source,
                        owner=owner
                    )
                    db.add(new_sess)

                # Activities upsert
                act_imported_count = 0
                act_updated_count = 0
                for idx, a_dict in enumerate(unique_acts, start=1):
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
                        act_updated_count += 1
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
                        act_imported_count += 1

                db.commit()

                # Increment counters ONLY AFTER successful commit
                if is_session_update:
                    updated_sessions += 1
                else:
                    imported_sessions += 1
                imported_activities += act_imported_count
                updated_activities += act_updated_count

            except Exception as e:
                db.rollback()
                failed_sessions.append((sid, str(e)))
            finally:
                db.close()
        else:
            imported_sessions += 1
            imported_activities += len(unique_acts)

        # Free memory for this session immediately
        sess_payload = None
        acts_raw = None
        unique_acts = None

    # Print summary
    mode_str = " (DRY-RUN)" if dry_run else ""
    print("=" * 70)
    print(f"JULES EXPORT IMPORT SUMMARY{mode_str}")
    print("=" * 70)
    print(f"Owner:      {owner}")
    print(f"Sources:    {imported_sources} new, {updated_sources} updated")
    print(f"Sessions:   {imported_sessions} new, {updated_sessions} updated")
    print(f"Activities: {imported_activities} new, {updated_activities} updated")

    if duplicates_discarded:
        print(f"Duplicates discarded (activities): {len(duplicates_discarded)}")
        for sid, aid in duplicates_discarded:
            print(f"  - Session {sid}, Activity {aid}")

    if fallback_sources:
        print(f"Fallback sources created: {len(fallback_sources)}")
        for sname in fallback_sources:
            print(f"  - {sname}")

    if session_conflicts:
        print(f"Session conflicts ignored: {len(session_conflicts)}")
        for sid, loc1, loc2 in session_conflicts:
            print(f"  - Session {sid}: used {loc1}, ignored {loc2}")

    if failed_sources:
        print(f"Failed sources: {len(failed_sources)}")
        for src, err in failed_sources:
            print(f"  - Source {src}: {err}")

    if failed_sessions:
        print(f"Failed sessions: {len(failed_sessions)}")
        for sid, err in failed_sessions:
            print(f"  - Session {sid}: {err}")

    print("=" * 70)

    if failed_sessions or failed_sources:
        return 1
    if partial_import_occurred:
        return 3
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import Jules Session Export Archives or Directories")
    parser.add_argument("paths", nargs="+", type=str, help="Path(s) to export directory or ZIP archive files")
    parser.add_argument(
        "--owner",
        type=str,
        required=True,
        help="Owner ID for imported sessions (must match --owner used in create_jules_api_key.py)"
    )
    parser.add_argument("--dry-run", action="store_true", help="Simulate import without writing to DB")
    parser.add_argument("--allow-partial", action="store_true", help="Allow partial import if expected sessions are missing")

    args = parser.parse_args()
    ret_code = import_jules_export(
        args.paths,
        owner=args.owner,
        dry_run=args.dry_run,
        allow_partial=args.allow_partial
    )
    sys.exit(ret_code)
