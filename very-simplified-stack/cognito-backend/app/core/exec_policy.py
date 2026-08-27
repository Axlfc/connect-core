import hashlib
import re
import sqlite3
from enum import Enum
from typing import List, Optional, Set, Tuple, Any, Dict

class ExecVerdict(str, Enum):
    PERMITIR = "permitir"
    DENEGAR = "denegar"
    REQUIERE_APROBACION = "requiere_aprobacion"


DANGEROUS_PREFIXES_AND_PATTERNS = [
    r"rm\s+-rf\s+/",
    r"rm\s+-[^ ]*r[^ ]*f\s+/",
    r"curl\s+.*\|\s*(bash|sh)",
    r"wget\s+.*\|\s*(bash|sh)",
    r"\bsudo\b",
    r"python\s+-c",
    r"python3\s+-c",
    r"mkfs",
    r"dd\s+if=",
    r":\(\)\{\s*:\|\:&\s*\};:",  # fork bomb
]

SENSITIVE_PREFIXES_AND_PATTERNS = [
    r"rm\s+-rf",
    r"rm\s+-[^ ]*r[^ ]*f",
    r"git\s+reset\s+--hard",
    r"git\s+clean",
    r"chmod\s+-R",
    r"chown\s+-R",
    r"\bkill\b",
    r"\bpkill\b",
    r"systemctl",
    r"service\s+",
    r"pip\s+install",
    r"npm\s+install",
    r"apt-get",
    r"yum\s+",
]

class ExecPolicy:
    """
    Engine for checking shell command risk policies.
    Classifies command execution into three verdicts:
    - ExecVerdict.DENEGAR ("denegar"): Hard forbidden/unconditional dangerous command patterns.
    - ExecVerdict.REQUIERE_APROBACION ("requiere_aprobacion"): Sensitive actions (destructive commands,
      system package operations, hard git resets) or execution in untrusted project context.
    - ExecVerdict.PERMITIR ("permitir"): Safe commands in a trusted environment.
    """
    def __init__(
        self,
        dangerous_patterns: Optional[List[str]] = None,
        sensitive_patterns: Optional[List[str]] = None,
    ):
        self.dangerous_patterns = dangerous_patterns or DANGEROUS_PREFIXES_AND_PATTERNS
        self.sensitive_patterns = sensitive_patterns or SENSITIVE_PREFIXES_AND_PATTERNS

    def is_dangerous(self, command: str) -> bool:
        """
        Returns True if command contains any forbidden/dangerous pattern (DENEGAR).
        """
        cmd_strip = command.strip()
        for pattern in self.dangerous_patterns:
            if re.search(pattern, cmd_strip, re.IGNORECASE):
                return True
        return False

    def is_sensitive(self, command: str) -> bool:
        """
        Returns True if command contains sensitive patterns requiring approval (REQUIERE_APROBACION).
        """
        cmd_strip = command.strip()
        for pattern in self.sensitive_patterns:
            if re.search(pattern, cmd_strip, re.IGNORECASE):
                return True
        return False

    def evaluate(self, command: str, project_trusted: bool = False) -> ExecVerdict:
        """
        Evaluates command against policy criteria and returns ExecVerdict.
        """
        if self.is_dangerous(command):
            return ExecVerdict.DENEGAR
        if self.is_sensitive(command) or not project_trusted:
            return ExecVerdict.REQUIERE_APROBACION
        return ExecVerdict.PERMITIR

    def requires_explicit_approval(self, command: str, project_trusted: bool = False) -> bool:
        """
        Helper method returning True if evaluation requires explicit user approval.
        """
        return self.evaluate(command, project_trusted=project_trusted) == ExecVerdict.REQUIERE_APROBACION


class SessionApprovalCache:
    """
    In-memory or SQLite-backed approval cache for commands within a session.
    When a user approves a specific command in a session, its hash is stored.
    Subsequent executions of the same command in the same session can be auto-approved.
    """
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path
        self._in_memory_cache: dict[str, Set[str]] = {}
        if self.db_path:
            self._init_sqlite()

    def _init_sqlite(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS session_approvals (
                    session_id TEXT NOT NULL,
                    cmd_hash TEXT NOT NULL,
                    PRIMARY KEY (session_id, cmd_hash)
                )
                """
            )

    @staticmethod
    def hash_command(command: str) -> str:
        """
        Generates a SHA-256 hash for a normalized command string.
        """
        normalized = command.strip()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def approve(self, session_id: str, command: str) -> None:
        """
        Records user approval for a given command in a session.
        """
        cmd_hash = self.hash_command(command)
        if self.db_path:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO session_approvals (session_id, cmd_hash) VALUES (?, ?)",
                    (session_id, cmd_hash)
                )
        else:
            if session_id not in self._in_memory_cache:
                self._in_memory_cache[session_id] = set()
            self._in_memory_cache[session_id].add(cmd_hash)

    def is_approved(self, session_id: str, command: str) -> bool:
        """
        Checks if a command has been previously approved in the given session.
        """
        if not session_id:
            return False
        cmd_hash = self.hash_command(command)
        if self.db_path:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT 1 FROM session_approvals WHERE session_id = ? AND cmd_hash = ?",
                    (session_id, cmd_hash)
                )
                return cur.fetchone() is not None
        else:
            return cmd_hash in self._in_memory_cache.get(session_id, set())

    def clear_session(self, session_id: str) -> None:
        """
        Clears approved command hashes for a session.
        """
        if self.db_path:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM session_approvals WHERE session_id = ?", (session_id,))
        else:
            self._in_memory_cache.pop(session_id, None)


def evaluate_command_execution(
    command: str,
    cwd: Optional[str] = None,
    trusted: bool = False,
    session_id: str = "default_session",
    user_approved: bool = False,
    exec_policy: Optional[ExecPolicy] = None,
    approval_cache: Optional[SessionApprovalCache] = None,
) -> Tuple[ExecVerdict, str]:
    """
    Unified evaluator for shell command execution.
    Combines evaluate_shell_command_policy, ExecPolicy, ProjectTrustStore permissions,
    and SessionApprovalCache.

    Returns:
        (verdict, reason)
        - ExecVerdict.PERMITIR: Execution proceeds.
        - ExecVerdict.REQUIERE_APROBACION: Execution requires human approval before running.
        - ExecVerdict.DENEGAR: Hard denied execution.
    """
    from app.core.shell_policy import evaluate_shell_command_policy
    from app.core.project_trust import ProjectTrustStore

    policy = exec_policy or default_exec_policy
    cache = approval_cache or session_approval_cache

    # 1. Obtain granular permissions for cwd or fallback to simple trust boolean
    if cwd:
        trust_store = ProjectTrustStore()
        permissions = trust_store.get_permissions(cwd)
    else:
        from app.core.project_trust import DEFAULT_LEGACY_TRUSTED, DEFAULT_NEW_UNTRUSTED
        permissions = DEFAULT_LEGACY_TRUSTED.copy() if trusted else DEFAULT_NEW_UNTRUSTED.copy()

    # 2. Evaluate against granular shell command policy
    classification = evaluate_shell_command_policy(command, permissions)

    # Hard rejection for unconditional deny patterns (e.g. sudo, rm -rf /, etc.)
    if classification.is_denied or policy.is_dangerous(command):
        return ExecVerdict.DENEGAR, f"Command forbidden by shell policy: {classification.reason or 'dangerous command pattern'}"

    # 3. Check session cache or explicit user approval
    is_cache_approved = cache.is_approved(session_id, command)
    if user_approved:
        cache.approve(session_id, command)

    auto_approved = is_cache_approved or user_approved
    if auto_approved:
        return ExecVerdict.PERMITIR, "Approved by session cache or user approval"

    # 4. Check whether ExecPolicy or shell policy requires explicit approval
    verdict = policy.evaluate(command, project_trusted=trusted)
    if classification.requires_approval or verdict == ExecVerdict.REQUIERE_APROBACION:
        reason_msg = (
            f"Command requires explicit user approval ({classification.reason or 'sensitive command or untrusted project'}). "
            f"Command: '{command}'."
        )
        return ExecVerdict.REQUIERE_APROBACION, reason_msg

    return ExecVerdict.PERMITIR, "Auto-approved by policy"


def evaluate_tool_execution(
    tool: Optional[Any] = None,
    arguments: Optional[dict] = None,
    command: Optional[str] = None,
    cwd: Optional[str] = None,
    trusted: bool = False,
    session_id: str = "default_session",
    user_approved: bool = False,
    exec_policy: Optional[ExecPolicy] = None,
    approval_cache: Optional[SessionApprovalCache] = None,
    turn: int = 1,
    planning_phase: bool = True,
    read_only_turns: int = 1,
) -> Tuple[ExecVerdict, str]:
    """
    Evaluates execution of an AgentTool or command using tool metadata (is_read_only, is_destructive),
    read-only planning phase policy, and command policy.
    """
    args = arguments or {}
    cmd = command or (args.get("command", "") if isinstance(args, dict) else "")

    is_read_only = getattr(tool, "is_read_only", False) if tool is not None else False
    tool_name = getattr(tool, "name", tool.__class__.__name__) if tool is not None else "tool"

    # Enforce read-only planning phase for untrusted workspaces during initial turns
    if planning_phase and not trusted and turn <= read_only_turns:
        if not is_read_only:
            return ExecVerdict.DENEGAR, (
                f"Fase de planificación de solo lectura activa (turno {turn}/{read_only_turns}): "
                f"la herramienta '{tool_name}' no es de solo lectura. "
                "Debe generar un plan antes de realizar modificaciones en un workspace no confiado."
            )

    if cmd:
        return evaluate_command_execution(
            command=cmd,
            cwd=cwd,
            trusted=trusted,
            session_id=session_id,
            user_approved=user_approved,
            exec_policy=exec_policy,
            approval_cache=approval_cache,
        )

    if tool is not None:
        is_destructive = getattr(tool, "is_destructive", False)

        if is_destructive and not trusted and not user_approved:
            return ExecVerdict.REQUIERE_APROBACION, f"Herramienta destructiva '{tool_name}' requiere aprobación en contexto no confiable."

        return ExecVerdict.PERMITIR, f"Auto-aprobado por metadatos de herramienta ({'solo lectura' if is_read_only else 'no destructiva'})"

    return ExecVerdict.PERMITIR, "Auto-aprobado por defecto"


# Default global instances
default_exec_policy = ExecPolicy()
session_approval_cache = SessionApprovalCache()
