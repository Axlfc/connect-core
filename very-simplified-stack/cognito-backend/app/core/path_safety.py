import os
from pathlib import Path
from typing import Optional


def is_path_contained(target_path: str, base_path: str) -> bool:
    """
    Checks if target_path is strictly inside base_path.
    Resolves canonical paths and symbolic links safely.
    Uses commonpath containment check.
    """
    try:
        # Null byte protection
        if '\x00' in target_path or '\x00' in base_path:
            return False

        # Resolve canonical paths (absolute and resolving symlinks)
        abs_base = os.path.realpath(base_path)
        abs_target = os.path.realpath(target_path)

        # Common path check
        common = os.path.commonpath([abs_base, abs_target])

        # If common is equal to abs_base, then abs_target is inside abs_base
        return common == abs_base
    except Exception:
        return False


def resolve_in_workspace(path: str, cwd: str) -> Optional[Path]:
    """
    Safely resolves a path relative to cwd inside workspace.
    - Rejects null bytes and absolute paths.
    - Resolves symbolic links and relative path traversals via realpath.
    - Ensures resolved target is contained within the canonical cwd.
    - Returns resolved Path object if safe, or None if path escapes workspace.
    """
    try:
        if not path or not isinstance(path, str) or '\x00' in path:
            return None

        # Reject absolute paths directly to prevent referencing root paths
        p = Path(path)
        if p.is_absolute():
            return None

        abs_cwd = os.path.realpath(cwd)
        joined_target = os.path.join(abs_cwd, path)
        resolved_target = os.path.realpath(joined_target)

        if not is_path_contained(resolved_target, abs_cwd):
            return None

        return Path(resolved_target)
    except Exception:
        return None
