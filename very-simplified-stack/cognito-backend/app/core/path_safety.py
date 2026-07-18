import os

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
