import asyncio
from pathlib import Path
from typing import Any, Dict, List, Tuple
from app.core.tools.base import AgentTool, ToolContext, ToolResult


def extract_diff_paths(patch_content: str) -> List[str]:
    """
    Extract target file paths referenced in unified diff headers ('---' and '+++').

    Args:
        patch_content: Standard unified diff text.

    Returns:
        List of candidate file path strings found in the headers.
    """
    paths: List[str] = []
    for line in patch_content.splitlines():
        if line.startswith("--- ") or line.startswith("+++ "):
            # Strip header identifier
            raw = line[4:].strip()
            # Remove timestamp or tab separator if present
            if "\t" in raw:
                raw = raw.split("\t", 1)[0].strip()
            # Strip enclosing quotes if present
            raw = raw.strip("\"'")
            # Skip empty paths or dev null
            if not raw or raw == "/dev/null" or raw.startswith("/dev/null"):
                continue

            # Strip standard git diff prefixes (a/ or b/)
            clean_path = raw
            if raw.startswith("a/") or raw.startswith("b/"):
                clean_path = raw[2:]

            paths.append(clean_path)
            if clean_path != raw:
                paths.append(raw)

    return paths


def validate_patch_security(patch_content: str, context: ToolContext) -> Tuple[bool, str]:
    """
    Validates security constraints before applying a patch:
    1. Project trust status.
    2. Path traversal check ensuring all paths resolve inside context.cwd.
    3. Protected files check ensuring no modified path is in context.protected_files.

    Args:
        patch_content: Unified diff content.
        context: ToolContext containing cwd, trust status, and protected files.

    Returns:
        Tuple of (is_valid, error_message).
    """
    if not context.trusted:
        return False, "Proyecto no confiado (untrusted). Ejecuta project-trust set antes de escribir."

    cwd_path = Path(context.cwd).resolve()
    candidate_paths = extract_diff_paths(patch_content)

    if not candidate_paths:
        return False, "Error: No valid file paths found in patch."

    for raw_path in candidate_paths:
        path_obj = Path(raw_path)

        if path_obj.is_absolute():
            target_path = path_obj.resolve()
        else:
            target_path = (cwd_path / path_obj).resolve()

        # Path traversal prevention using pathlib
        try:
            if not target_path.is_relative_to(cwd_path):
                return False, f"Error: Access denied. Path '{raw_path}' is outside of workspace."
        except ValueError:
            return False, f"Error: Access denied. Path '{raw_path}' is outside of workspace."

        # Check protected files
        try:
            rel_path = target_path.relative_to(cwd_path).as_posix()
        except ValueError:
            return False, f"Error: Access denied. Path '{raw_path}' is outside of workspace."

        norm_raw = Path(raw_path).as_posix()

        if rel_path in context.protected_files or norm_raw in context.protected_files:
            return False, f"Archivo protegido: {rel_path}. No se puede modificar vía agente."

    return True, ""


async def apply_patch_atomically(patch_content: str, cwd_path: Path) -> ToolResult:
    """
    Applies a patch atomically using 'git apply --check' followed by 'git apply'.
    If git is unavailable, falls back to Python's patch library.

    Args:
        patch_content: Unified diff text.
        cwd_path: Resolved absolute Path of current workspace directory.

    Returns:
        ToolResult indicating success or detailed failure error.
    """
    patch_bytes = patch_content.encode("utf-8")

    try:
        # Step 1: Validate patch application atomically without modifying files
        check_proc = await asyncio.create_subprocess_exec(
            "git", "apply", "--check", "-",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd_path)
        )
        _, stderr_check = await check_proc.communicate(input=patch_bytes)

        if check_proc.returncode != 0:
            err_msg = stderr_check.decode("utf-8", errors="replace").strip()
            return ToolResult(
                is_error=True,
                output=f"Error checking patch (context out of date or invalid hunk):\n{err_msg}"
            )

        # Step 2: Apply patch cleanly
        apply_proc = await asyncio.create_subprocess_exec(
            "git", "apply", "-",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd_path)
        )
        _, stderr_apply = await apply_proc.communicate(input=patch_bytes)

        if apply_proc.returncode != 0:
            err_msg = stderr_apply.decode("utf-8", errors="replace").strip()
            return ToolResult(
                is_error=True,
                output=f"Error applying patch:\n{err_msg}"
            )

        return ToolResult(output="Patch applied successfully.")

    except FileNotFoundError:
        # Fallback if git executable is not available in environment
        return _apply_patch_python_fallback(patch_content, cwd_path)
    except Exception as e:
        return ToolResult(is_error=True, output=f"Unexpected error applying patch: {str(e)}")


def _apply_patch_python_fallback(patch_content: str, cwd_path: Path) -> ToolResult:
    """
    Fallback patch application using Python's 'patch' module if git is missing.
    """
    try:
        import patch
        pset = patch.fromstring(patch_content.encode("utf-8"))
        if not pset:
            return ToolResult(is_error=True, output="Error parsing patch with python patch library.")

        success = pset.apply(strip=1, root=str(cwd_path))
        if not success:
            return ToolResult(is_error=True, output="Error applying patch via fallback patch library.")
        return ToolResult(output="Patch applied successfully using fallback library.")
    except Exception as e:
        return ToolResult(is_error=True, output=f"Error applying patch via fallback: {str(e)}")


class UnifiedPatchTool(AgentTool):
    """
    Agent tool that applies standard Unified Diff patches to workspace files securely and atomically.
    Prevents path traversal and modification of protected files.
    """
    name = "unified_patch"
    description = (
        "Apply a unified diff patch (with ---/+++ headers and @@ hunks) to workspace files. "
        "Validates path safety and protected files prior to application."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "patch": {
                "type": "string",
                "description": "Standard Unified Diff patch content."
            }
        },
        "required": ["patch"],
    }

    async def execute(self, arguments: Dict[str, Any], context: ToolContext) -> ToolResult:
        patch_content = arguments.get("patch")
        if not patch_content or not isinstance(patch_content, str):
            return ToolResult(
                is_error=True,
                output="Error: 'patch' parameter is required and must be a non-empty string."
            )

        # Validate security before making any filesystem modifications
        is_safe, error_message = validate_patch_security(patch_content, context)
        if not is_safe:
            return ToolResult(is_error=True, output=error_message)

        cwd_path = Path(context.cwd).resolve()
        return await apply_patch_atomically(patch_content, cwd_path)
