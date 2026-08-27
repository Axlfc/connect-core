import os
import re
import subprocess
import shutil
import logging
from pathlib import Path
from typing import List, Tuple, Optional
from urllib.parse import urlparse

logger = logging.getLogger("cognito.worker.worktree")

# Allowed repository URL schemes for git operations
ALLOWED_REPO_SCHEMES = {"https", "http", "ssh", "git"}
# Unsafe git URL protocols that can execute arbitrary commands
FORBIDDEN_PROTOCOLS = {"ext", "fd", "file"}

def validate_repo_url_or_path(url_or_path: str) -> str:
    """
    Validates a Git repository URL or local directory path.
    Prevents flag injection (strings starting with '-') and dangerous schemes (e.g. ext::).
    """
    if not url_or_path or not isinstance(url_or_path, str):
        raise ValueError("Repository path/URL must be a non-empty string.")

    if "\x00" in url_or_path:
        raise ValueError("Null bytes are not allowed in repository path/URL.")

    cleaned = url_or_path.strip()

    if cleaned.startswith("-"):
        raise ValueError(f"Invalid repository path/URL '{url_or_path}': cannot start with '-'.")

    # Check for git transport protocol wrappers (e.g., ext::, fd::)
    if "::" in cleaned:
        prefix = cleaned.split("::", 1)[0].lower()
        if prefix in FORBIDDEN_PROTOCOLS or prefix not in ALLOWED_REPO_SCHEMES:
            raise ValueError(f"Forbidden or untrusted Git protocol scheme in '{url_or_path}'.")

    # Check parsed URL scheme if it resembles a URL
    if "://" in cleaned:
        parsed = urlparse(cleaned)
        scheme = parsed.scheme.lower() if parsed.scheme else ""
        if scheme in FORBIDDEN_PROTOCOLS or (scheme and scheme not in ALLOWED_REPO_SCHEMES):
            raise ValueError(f"Forbidden or untrusted Git URL scheme '{scheme}' in '{url_or_path}'.")

    return cleaned

def validate_git_ref(ref_name: str, name_label: str = "Git reference") -> str:
    """
    Validates a Git branch, tag, or commit reference name.
    Rejects flags (starting with '-'), null bytes, and invalid ref characters.
    """
    if not ref_name or not isinstance(ref_name, str):
        raise ValueError(f"{name_label} must be a non-empty string.")

    if "\x00" in ref_name:
        raise ValueError(f"Null bytes are not allowed in {name_label}.")

    cleaned = ref_name.strip()

    if cleaned.startswith("-"):
        raise ValueError(f"Invalid {name_label} '{ref_name}': cannot start with '-'.")

    # Reject whitespace and control characters
    if re.search(r"\s", cleaned):
        raise ValueError(f"Invalid {name_label} '{ref_name}': contains whitespace.")

    # Reject invalid git ref sequences: .., ~, ^, :, ?, *, [, \, @{
    if re.search(r"\.\.|[~^:?\*\[\\]|@\{", cleaned):
        raise ValueError(f"Invalid {name_label} '{ref_name}': contains invalid git ref characters.")

    if cleaned.endswith(".lock") or cleaned.endswith("/") or cleaned.endswith("."):
        raise ValueError(f"Invalid {name_label} '{ref_name}': ends with invalid suffix.")

    return cleaned

def validate_identifier(identifier: str, name_label: str = "Identifier") -> str:
    """
    Validates generic identifiers such as repo_id or task_id.
    Ensures alphanumeric with hyphens/underscores/dots only, and never starting with '-'.
    """
    if not identifier or not isinstance(identifier, str):
        raise ValueError(f"{name_label} must be a non-empty string.")

    if "\x00" in identifier:
        raise ValueError(f"Null bytes are not allowed in {name_label}.")

    cleaned = identifier.strip()

    if cleaned.startswith("-"):
        raise ValueError(f"Invalid {name_label} '{identifier}': cannot start with '-'.")

    if not re.match(r"^[a-zA-Z0-9_\-\.]+$", cleaned):
        raise ValueError(f"Invalid {name_label} '{identifier}': contains disallowed characters.")

    return cleaned


class GitWorktreeManager:
    def __init__(self, base_worktree_dir: Optional[Path] = None):
        self.base_dir = base_worktree_dir or (Path.home() / ".cognito" / "worktrees")
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _run_git(self, repo_path: str, args: List[str]) -> Tuple[int, str, str]:
        validated_path = validate_repo_url_or_path(repo_path)
        # Ensure no empty strings in args that could confuse option parsing
        clean_args = [arg for arg in args if arg != ""]
        try:
            res = subprocess.run(
                ["git"] + clean_args,
                cwd=validated_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=15
            )
            return res.returncode, res.stdout.strip(), res.stderr.strip()
        except subprocess.TimeoutExpired:
            return -1, "", "Git command timed out"
        except Exception as e:
            return -1, "", str(e)

    def validate_git_repo(self, repo_path: str) -> str:
        """
        Validates target is a Git repository and returns its current HEAD commit.
        """
        validated_path = validate_repo_url_or_path(repo_path)
        code, out, err = self._run_git(validated_path, ["rev-parse", "--is-inside-work-tree"])
        if code != 0 or out != "true":
            raise ValueError(f"Path '{repo_path}' is not a valid Git repository.")

        code, head_commit, err = self._run_git(validated_path, ["rev-parse", "--verify", "HEAD"])
        if code != 0:
            raise ValueError(f"Failed to resolve HEAD commit: {err}")

        validate_git_ref(head_commit, "HEAD commit")
        return head_commit

    def is_dirty(self, repo_path: str) -> bool:
        validated_path = validate_repo_url_or_path(repo_path)
        code, out, err = self._run_git(validated_path, ["status", "--porcelain"])
        return code == 0 and bool(out)

    def create_worktree(self, base_repo_path: str, repo_id: str, task_id: str, attempt: int) -> Tuple[str, str]:
        """
        Creates a dedicated Git worktree for the task attempt.
        Returns Tuple of (worktree_absolute_path, branch_name).
        """
        validated_base = validate_repo_url_or_path(base_repo_path)
        clean_repo_id = validate_identifier(repo_id, "repo_id")
        clean_task_id = validate_identifier(task_id, "task_id")

        base_commit = self.validate_git_repo(validated_base)

        # Structure: ~/.cognito/worktrees/<repo-id>/<task-id>/attempt-XX/
        worktree_path = self.base_dir / clean_repo_id / clean_task_id / f"attempt-{attempt:02d}"
        worktree_path.parent.mkdir(parents=True, exist_ok=True)

        branch_name = f"cognito/task-{clean_task_id}-attempt-{attempt:02d}"
        validate_git_ref(branch_name, "branch_name")

        # 1. Create collision-safe branch in the base repo using '--' separator
        code, out, err = self._run_git(validated_base, ["branch", "--", branch_name, base_commit])
        if code != 0:
            # If branch already exists, we can use it or fail
            logger.info(f"Branch '{branch_name}' already exists, continuing.")

        # 2. Add worktree using '--' separator
        code, out, err = self._run_git(validated_base, ["worktree", "add", "--", str(worktree_path), branch_name])
        if code != 0:
            # Clean up the branch if we just created it and worktree addition failed
            self._run_git(validated_base, ["branch", "-d", "--", branch_name])
            raise RuntimeError(f"Failed to create Git worktree: {err}")

        logger.info(f"Created worktree at '{worktree_path}' on branch '{branch_name}'")
        return str(worktree_path.resolve()), branch_name

    def get_diff(self, worktree_path: str, base_commit: str) -> str:
        """
        Gets the diff of the worktree against the starting base commit.
        """
        validated_wt = validate_repo_url_or_path(worktree_path)
        validated_commit = validate_git_ref(base_commit, "base_commit")
        code, out, err = self._run_git(validated_wt, ["diff", validated_commit])
        return out

    def get_untracked_diff(self, worktree_path: str) -> str:
        validated_wt = validate_repo_url_or_path(worktree_path)
        code, out, err = self._run_git(validated_wt, ["status", "--porcelain"])
        return out

    def has_uncommitted_changes(self, worktree_path: str) -> bool:
        return self.is_dirty(worktree_path)

    def cleanup_worktree(self, base_repo_path: str, worktree_path: str, force: bool = False) -> None:
        """
        Safely removes a Git worktree.
        Never deletes a worktree containing uncommitted results unless force=True.
        """
        validated_base = validate_repo_url_or_path(base_repo_path)
        validated_wt = validate_repo_url_or_path(worktree_path)

        p = Path(validated_wt)
        if not p.exists():
            return

        if self.has_uncommitted_changes(validated_wt) and not force:
            logger.warning(f"Worktree at '{validated_wt}' has uncommitted changes. Skipping deletion to protect progress.")
            return

        # Prune and remove worktree safely without empty string args
        cmd = ["worktree", "remove"]
        if force:
            cmd.append("--force")
        cmd.extend(["--", str(p)])

        code, out, err = self._run_git(validated_base, cmd)
        if code != 0:
            # Fallback to physical deletion if git worktree remove fails or complains
            try:
                shutil.rmtree(p)
                self._run_git(validated_base, ["worktree", "prune"])
            except Exception as e:
                logger.error(f"Failed to physically clean worktree at '{validated_wt}': {e}")
        else:
            logger.info(f"Successfully removed worktree at '{validated_wt}'")

    def recover_orphaned_worktrees(self, base_repo_path: str) -> List[str]:
        """
        Scans registered worktrees in the base repo and prunes any that no longer exist physically.
        """
        validated_base = validate_repo_url_or_path(base_repo_path)
        code, out, err = self._run_git(validated_base, ["worktree", "prune"])
        return []
