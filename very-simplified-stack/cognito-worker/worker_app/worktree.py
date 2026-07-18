import os
import subprocess
import shutil
import logging
from pathlib import Path
from typing import List, Tuple, Optional

logger = logging.getLogger("cognito.worker.worktree")

class GitWorktreeManager:
    def __init__(self, base_worktree_dir: Optional[Path] = None):
        self.base_dir = base_worktree_dir or (Path.home() / ".cognito" / "worktrees")
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _run_git(self, repo_path: str, args: List[str]) -> Tuple[int, str, str]:
        try:
            res = subprocess.run(
                ["git"] + args,
                cwd=repo_path,
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
        code, out, err = self._run_git(repo_path, ["rev-parse", "--is-inside-work-tree"])
        if code != 0 or out != "true":
            raise ValueError(f"Path '{repo_path}' is not a valid Git repository.")

        code, head_commit, err = self._run_git(repo_path, ["rev-parse", "HEAD"])
        if code != 0:
            raise ValueError(f"Failed to resolve HEAD commit: {err}")

        return head_commit

    def is_dirty(self, repo_path: str) -> bool:
        code, out, err = self._run_git(repo_path, ["status", "--porcelain"])
        return code == 0 and bool(out)

    def create_worktree(self, base_repo_path: str, repo_id: str, task_id: str, attempt: int) -> Tuple[str, str]:
        """
        Creates a dedicated Git worktree for the task attempt.
        Returns Tuple of (worktree_absolute_path, branch_name).
        """
        base_commit = self.validate_git_repo(base_repo_path)

        # Structure: ~/.cognito/worktrees/<repo-id>/<task-id>/attempt-XX/
        worktree_path = self.base_dir / repo_id / task_id / f"attempt-{attempt:02d}"
        worktree_path.parent.mkdir(parents=True, exist_ok=True)

        branch_name = f"cognito/task-{task_id}-attempt-{attempt:02d}"

        # 1. Create collision-safe branch in the base repo
        code, out, err = self._run_git(base_repo_path, ["branch", branch_name, base_commit])
        if code != 0:
            # If branch already exists, we can use it or fail
            logger.info(f"Branch '{branch_name}' already exists, continuing.")

        # 2. Add worktree
        code, out, err = self._run_git(base_repo_path, ["worktree", "add", str(worktree_path), branch_name])
        if code != 0:
            # Clean up the branch if we just created it and worktree addition failed
            self._run_git(base_repo_path, ["branch", "-d", branch_name])
            raise RuntimeError(f"Failed to create Git worktree: {err}")

        logger.info(f"Created worktree at '{worktree_path}' on branch '{branch_name}'")
        return str(worktree_path.resolve()), branch_name

    def get_diff(self, worktree_path: str, base_commit: str) -> str:
        """
        Gets the diff of the worktree against the starting base commit.
        """
        # Ensure changes are staged/committed internally or just diff tracked/untracked files
        code, out, err = self._run_git(worktree_path, ["diff", base_commit])
        return out

    def get_untracked_diff(self, worktree_path: str) -> str:
        # Include untracked files in the diff
        code, out, err = self._run_git(worktree_path, ["status", "--porcelain"])
        return out

    def has_uncommitted_changes(self, worktree_path: str) -> bool:
        # Check if there are dirty/uncommitted modifications inside the worktree
        return self.is_dirty(worktree_path)

    def cleanup_worktree(self, base_repo_path: str, worktree_path: str, force: bool = False) -> None:
        """
        Safely removes a Git worktree.
        Never deletes a worktree containing uncommitted results unless force=True.
        """
        p = Path(worktree_path)
        if not p.exists():
            return

        if self.has_uncommitted_changes(worktree_path) and not force:
            logger.warning(f"Worktree at '{worktree_path}' has uncommitted changes. Skipping deletion to protect progress.")
            return

        # Prune and remove worktree
        code, out, err = self._run_git(base_repo_path, ["worktree", "remove", "--force" if force else "", str(p)])
        if code != 0:
            # Fallback to physical deletion if git worktree remove fails or complains
            try:
                shutil.rmtree(p)
                self._run_git(base_repo_path, ["worktree", "prune"])
            except Exception as e:
                logger.error(f"Failed to physically clean worktree at '{worktree_path}': {e}")
        else:
            logger.info(f"Successfully removed worktree at '{worktree_path}'")

    def recover_orphaned_worktrees(self, base_repo_path: str) -> List[str]:
        """
        Scans registered worktrees in the base repo and prunes any that no longer exist physically.
        """
        code, out, err = self._run_git(base_repo_path, ["worktree", "prune"])
        return []
