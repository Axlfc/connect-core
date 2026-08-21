import asyncio
import os
import re
from typing import Any, Dict, List, Tuple
from app.core.tools.base import AgentTool, ToolContext, ToolResult

REVIEW_PROMPT_HEADER = (
    "Analiza este diff buscando bugs, vulnerabilidades de seguridad, o desviaciones de las instrucciones de AGENTS.md. "
    "Devuelve un JSON estructurado con: archivo, línea, severidad, y explicación."
)

MAX_DIFF_CHARS_DEFAULT = 12000


class CodeReviewTool(AgentTool):
    name = "code_review"
    description = (
        "Revisa cambios de código (diff) para identificar bugs, vulnerabilidades de seguridad o "
        "desviaciones de AGENTS.md. Acepta objetivos como 'uncommitted', 'branch:main', o 'commit:abc123'."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": (
                    "Target to diff, e.g., 'uncommitted', 'branch:main', 'commit:abc123', or git ref/range."
                ),
                "default": "uncommitted",
            },
            "max_characters": {
                "type": "integer",
                "description": "Maximum character limit before truncating/summarizing large diffs.",
                "default": MAX_DIFF_CHARS_DEFAULT,
            },
        },
    }

    async def _run_git_cmd(self, args: List[str], cwd: str) -> Tuple[int, str, str]:
        """Safely execute git subcommand using create_subprocess_exec without shell execution."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "git",
                *args,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            return proc.returncode or 0, stdout.decode("utf-8", errors="replace"), stderr.decode("utf-8", errors="replace")
        except Exception as e:
            return 1, "", str(e)

    def _sanitize_git_ref(self, ref: str) -> str:
        """Sanitize ref to prevent argument injection."""
        cleaned = ref.strip()
        if cleaned.startswith("-"):
            raise ValueError(f"Invalid git reference: '{ref}' cannot start with '-'")
        if not re.match(r"^[a-zA-Z0-9_\-./~^:@]+$", cleaned):
            raise ValueError(f"Invalid git reference characters in: '{ref}'")
        return cleaned

    async def _resolve_git_diff_args(self, target: str, cwd: str) -> Tuple[List[str], str]:
        """
        Parses the target parameter into git diff command arguments and a human-readable summary.
        Supported target formats:
        - "uncommitted" or "" -> HEAD diff (or unstaged/staged diff)
        - "branch:<name>" -> diff from merge-base with HEAD
        - "commit:<hash>" -> diff for that single commit (<hash>~1..<hash>)
        - raw ref / range (e.g. "main", "HEAD~1..HEAD")
        """
        target = (target or "uncommitted").strip()

        if target in ("uncommitted", "staged", "working"):
            # Check if HEAD exists in repository
            code, _, _ = await self._run_git_cmd(["rev-parse", "--verify", "HEAD"], cwd)
            if code == 0:
                return ["diff", "HEAD"], "uncommitted changes against HEAD"
            else:
                return ["diff"], "uncommitted changes (working directory)"

        if target.startswith("branch:"):
            raw_branch = target[len("branch:") :].strip()
            branch = self._sanitize_git_ref(raw_branch)
            # Find merge-base safely
            code, stdout, _ = await self._run_git_cmd(["merge-base", "HEAD", branch], cwd)
            if code == 0 and stdout.strip():
                merge_base = stdout.strip()
                return ["diff", f"{merge_base}..HEAD"], f"branch changes from merge-base ({branch})"
            else:
                return ["diff", f"{branch}...HEAD"], f"branch changes comparing with {branch}"

        if target.startswith("commit:"):
            raw_commit = target[len("commit:") :].strip()
            commit_ref = self._sanitize_git_ref(raw_commit)
            # Try commit~1..commit, fallback to show if no parent (e.g. initial commit)
            code, _, _ = await self._run_git_cmd(["rev-parse", "--verify", f"{commit_ref}~1"], cwd)
            if code == 0:
                return ["diff", f"{commit_ref}~1", commit_ref], f"changes introduced by commit {commit_ref}"
            else:
                return ["show", "--format=", commit_ref], f"commit details for {commit_ref}"

        # Raw ref or range
        ref = self._sanitize_git_ref(target)
        if ".." in ref:
            parts = ref.split("..")
            for p in parts:
                if p:
                    self._sanitize_git_ref(p)
            return ["diff", ref], f"diff range {ref}"

        return ["diff", ref], f"diff against {ref}"

    async def execute(self, arguments: Dict[str, Any], context: ToolContext) -> ToolResult:
        raw_target = str(arguments.get("target") or "uncommitted")
        max_chars = int(arguments.get("max_characters") or MAX_DIFF_CHARS_DEFAULT)

        if not os.path.isdir(context.cwd):
            return ToolResult(is_error=True, output=f"Error: Directory '{context.cwd}' does not exist.")

        # Verify git repo
        code, _, stderr = await self._run_git_cmd(["rev-parse", "--is-inside-work-tree"], context.cwd)
        if code != 0:
            return ToolResult(is_error=True, output=f"Error: '{context.cwd}' is not a valid git repository. {stderr.strip()}")

        try:
            diff_args, target_desc = await self._resolve_git_diff_args(raw_target, context.cwd)
        except ValueError as ve:
            return ToolResult(is_error=True, output=f"Error: {str(ve)}")

        # Obtain git diff output
        code, diff_output, stderr = await self._run_git_cmd(diff_args, context.cwd)
        if code != 0:
            return ToolResult(is_error=True, output=f"Error executing git diff for target '{raw_target}': {stderr.strip()}")

        if not diff_output.strip():
            return ToolResult(
                output=f"{REVIEW_PROMPT_HEADER}\n\nTarget: {target_desc}\n\nNo changes found in diff."
            )

        # Get diff stat summary
        stat_args = list(diff_args)
        if stat_args[0] == "diff":
            stat_args.insert(1, "--stat")
        else: # e.g. show
            stat_args.append("--stat")
        _, stat_output, _ = await self._run_git_cmd(stat_args, context.cwd)

        # Handle diff size
        if len(diff_output) > max_chars:
            truncated_diff = diff_output[:max_chars]
            # Truncate at last newline to avoid breaking mid-line
            last_newline = truncated_diff.rfind("\n")
            if last_newline > 0:
                truncated_diff = truncated_diff[:last_newline]

            content_text = (
                f"--- SUMMARY OF STATS ---\n{stat_output.strip()}\n\n"
                f"--- DIFF CONTENT (TRUNCATED to {max_chars} chars of {len(diff_output)} chars) ---\n"
                f"{truncated_diff}\n\n"
                f"[NOTE: Diff was too large and was truncated. Use specific files or commits if full detail is required.]"
            )
        else:
            content_text = (
                f"--- SUMMARY OF STATS ---\n{stat_output.strip()}\n\n"
                f"--- DIFF CONTENT ---\n"
                f"{diff_output.strip()}"
            )

        full_output = f"{REVIEW_PROMPT_HEADER}\n\nTarget description: {target_desc}\n\n{content_text}"

        return ToolResult(output=full_output)
