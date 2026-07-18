import os
import re
import shlex
from typing import Dict, List, Any, Literal

# Unconditional deny patterns or commands
UNCONDITIONAL_DENY_PATTERNS = [
    r"\bsudo\b",
    r"\brm\s+-[^ ]*r",    # rm -rf, rm -r, etc.
    r"\brm\s+--recursive\b",
    r"\|\s*(sh|bash|zsh|ksh|tcsh|csh)\b",  # piping into a shell
    r"git\s+push\s+-[^ ]*f",  # git push -f or git push --force
    r"git\s+push\s+--force\b",
    r"docker\s+volume\s+rm\b",
    r"docker\s+compose\s+down\b",
    r"\bdrop\s+database\b",
    r"\bdrop\s+table\b",
    r"\btruncate\s+table\b"
]

class CommandClassification:
    def __init__(self, command: str, category: str, reason: str, requires_approval: bool = True, is_denied: bool = False):
        self.command = command
        self.category = category
        self.reason = reason
        self.requires_approval = requires_approval
        self.is_denied = is_denied

def split_compound_commands(command: str) -> List[str]:
    """
    Split a compound shell command into individual simple commands.
    Extracts backticks and $(...) subcommands, and splits by operators (&&, ||, ;, |, \n).
    """
    subcommands = []
    # $(...)
    for m in re.findall(r'\$\(([^)]+)\)', command):
        subcommands.append(m)
    # backticks
    for m in re.findall(r'`([^`]+)`', command):
        subcommands.append(m)

    # Replace subcommands to avoid double-splitting
    clean_command = re.sub(r'\$\([^)]+\)', ' SUB_CMD ', command)
    clean_command = re.sub(r'`[^`]+`', ' SUB_CMD ', clean_command)

    # Split by &&, ||, |, ;, \n
    delimiters = ['&&', '||', '|', ';', '\n']
    pattern = '|'.join(map(re.escape, delimiters))
    parts = re.split(pattern, clean_command)

    all_cmds = subcommands + parts
    return [c.strip() for c in all_cmds if c.strip()]

def classify_simple_command(cmd_str: str) -> CommandClassification:
    # 1. Unconditional deny check
    for pattern in UNCONDITIONAL_DENY_PATTERNS:
        if re.search(pattern, cmd_str, re.IGNORECASE):
            return CommandClassification(
                command=cmd_str,
                category="destructive_operations",
                reason=f"Command matches unconditional deny pattern: {pattern}",
                requires_approval=True,
                is_denied=True
            )

    try:
        tokens = shlex.split(cmd_str)
    except Exception:
        # Lexer failure, conservative fallback
        return CommandClassification(
            command=cmd_str,
            category="unknown",
            reason="Failed to parse shell tokens, treated as unknown/compound",
            requires_approval=True,
            is_denied=False
        )

    if not tokens:
        return CommandClassification(
            command=cmd_str,
            category="read_only_inspection",
            reason="Empty command",
            requires_approval=False,
            is_denied=False
        )

    exe = os.path.basename(tokens[0]).lower()
    args = tokens[1:]

    # Sudo check just in case
    if exe == "sudo":
        return CommandClassification(
            command=cmd_str,
            category="destructive_operations",
            reason="Sudo execution is forbidden",
            requires_approval=True,
            is_denied=True
        )

    # Read-only inspection
    if exe in ["ls", "cat", "grep", "pwd", "head", "tail", "less", "more", "find", "echo", "whoami", "hostname", "date"]:
        return CommandClassification(
            command=cmd_str,
            category="read_only_inspection",
            reason="Read-only filesystem or context inspection",
            requires_approval=False,
            is_denied=False
        )

    # Tests
    if exe in ["pytest", "jest", "vitest", "playwright", "tox"] or (exe == "npm" and args and args[0] == "test"):
        return CommandClassification(
            command=cmd_str,
            category="tests",
            reason="Test runner execution",
            requires_approval=False,
            is_denied=False
        )

    # Linting
    if exe in ["eslint", "flake8", "pylint", "black", "autopep8", "prettier"] or (exe == "npm" and args and args[0] == "run" and len(args) > 1 and "lint" in args[1]):
        return CommandClassification(
            command=cmd_str,
            category="lint",
            reason="Code formatting or lint execution",
            requires_approval=False,
            is_denied=False
        )

    # Type checking
    if exe in ["mypy", "tsc"]:
        return CommandClassification(
            command=cmd_str,
            category="type_checking",
            reason="Static type checking execution",
            requires_approval=False,
            is_denied=False
        )

    # Git command tree
    if exe == "git":
        if not args:
            return CommandClassification(command=cmd_str, category="git_read", reason="Git inspection", requires_approval=False)
        sub = args[0].lower()
        if sub in ["status", "diff", "log", "show", "remote", "branch", "config"]:
            if "--force" in cmd_str or "-f" in cmd_str:
                return CommandClassification(command=cmd_str, category="destructive_operations", reason="Destructive git operation forbidden", requires_approval=True, is_denied=True)
            return CommandClassification(command=cmd_str, category="git_read", reason="Git read-only inspection", requires_approval=False)
        elif sub in ["add", "checkout", "commit", "reset", "clean", "merge", "rebase", "cherry-pick", "stash"]:
            return CommandClassification(command=cmd_str, category="git_commit", reason="Git repository modification", requires_approval=True)
        elif sub == "push":
            if "--force" in cmd_str or "-f" in cmd_str:
                return CommandClassification(command=cmd_str, category="destructive_operations", reason="Force git push forbidden", requires_approval=True, is_denied=True)
            return CommandClassification(command=cmd_str, category="git_push", reason="Git push to remote", requires_approval=True)
        else:
            return CommandClassification(command=cmd_str, category="git_commit", reason="Other Git command", requires_approval=True)

    # Filesystem Mutation
    if exe in ["touch", "mkdir", "cp", "mv", "rm"]:
        # rm -rf is already denied above, but RM is filesystem mutation
        return CommandClassification(
            command=cmd_str,
            category="filesystem_mutation",
            reason="Filesystem modification command",
            requires_approval=True
        )

    # Build tools
    if exe in ["make", "mvn", "gradle", "cmake", "gcc", "g++", "clang"] or (exe == "npm" and args and args[0] == "run" and len(args) > 1 and "build" in args[1]):
        return CommandClassification(
            command=cmd_str,
            category="build",
            reason="Software build execution",
            requires_approval=False
        )

    # Dependency Installation
    if exe in ["npm", "pip", "pip3", "poetry", "yarn", "pnpm", "apt", "apt-get", "pacman", "yum", "dnf", "gem", "cargo"]:
        if args and args[0] in ["install", "add", "update", "upgrade", "get"]:
            return CommandClassification(
                command=cmd_str,
                category="dependency_installation",
                reason="Package or dependency installation",
                requires_approval=True
            )

    # Network commands
    if exe in ["curl", "wget", "ping", "ssh", "scp", "rsync", "ftp", "sftp"]:
        return CommandClassification(
            command=cmd_str,
            category="network_access",
            reason="Network operation",
            requires_approval=True
        )

    # Process/service control
    if exe in ["systemctl", "service", "kill", "killall", "pkill", "ps", "top"]:
        return CommandClassification(
            command=cmd_str,
            category="process/service_control",
            reason="Process or service management",
            requires_approval=True
        )

    # Database mutation
    if exe in ["psql", "sqlite3", "mysql", "mongo"] or (exe == "flask" and args and "db" in args) or (exe == "alembic"):
        return CommandClassification(
            command=cmd_str,
            category="database_mutation",
            reason="Database query or migration command",
            requires_approval=True
        )

    # Container control
    if exe in ["docker", "docker-compose", "podman"]:
        return CommandClassification(
            command=cmd_str,
            category="container_control",
            reason="Container management execution",
            requires_approval=True
        )

    # Permissions change
    if exe in ["chmod", "chown", "chgrp"]:
        return CommandClassification(
            command=cmd_str,
            category="permission_changes",
            reason="Permissions or ownership modifications",
            requires_approval=True
        )

    # Destructive commands fallback
    if "drop" in exe or "truncate" in exe or "delete" in exe:
        return CommandClassification(
            command=cmd_str,
            category="destructive_operations",
            reason="Possibly destructive operation",
            requires_approval=True,
            is_denied=True
        )

    # Default fallback
    return CommandClassification(
        command=cmd_str,
        category="unknown",
        reason="Unknown program, treated conservatively",
        requires_approval=True
    )

def evaluate_shell_command_policy(command: str, permissions: Dict[str, Any]) -> CommandClassification:
    """
    Evaluates a command against repository granular permissions.
    Returns the strictest classification.
    """
    sub_cmds = split_compound_commands(command)
    if not sub_cmds:
        return CommandClassification(command=command, category="read_only_inspection", reason="Empty command", requires_approval=False)

    evaluated_classes = []

    for sc in sub_cmds:
        cl = classify_simple_command(sc)

        cl_requires_app = False
        cat = cl.category

        if cl.is_denied:
            cl_requires_app = True
        elif cat == "destructive_operations":
            cl_requires_app = not permissions.get("destructive_operations", False)
        elif cat == "unknown":
            cl_requires_app = True
        elif cat in ["git_commit", "git_push"]:
            perm_val = permissions.get(cat, "approval")
            cl_requires_app = (perm_val == "approval" or not perm_val)
        elif cat == "network_access":
            cl_requires_app = not permissions.get("network", False)
        elif cat == "dependency_installation":
            cl_requires_app = not (permissions.get("network", False) and permissions.get("write", False))
        elif cat in ["filesystem_mutation", "permission_changes", "database_mutation"]:
            cl_requires_app = not permissions.get("write", False)
        elif cat in ["container_control", "process/service_control"]:
            perm_val = permissions.get("shell", "approval")
            cl_requires_app = (perm_val == "approval" or not perm_val)
        elif cat in ["build"]:
            cl_requires_app = not permissions.get("write", False)
        else: # read_only_inspection, tests, lint, type_checking
            cl_requires_app = not permissions.get("read", True)

        cl.requires_approval = cl_requires_app
        evaluated_classes.append(cl)

    worst_class = evaluated_classes[0]
    for cl in evaluated_classes[1:]:
        if cl.is_denied and not worst_class.is_denied:
            worst_class = cl
        elif cl.requires_approval and not worst_class.requires_approval:
            worst_class = cl
        elif cl.requires_approval == worst_class.requires_approval:
            if cl.category in ["destructive_operations", "unknown"] and worst_class.category not in ["destructive_operations", "unknown"]:
                worst_class = cl
            elif cl.category == "destructive_operations" and worst_class.category == "unknown":
                worst_class = cl

    return worst_class
