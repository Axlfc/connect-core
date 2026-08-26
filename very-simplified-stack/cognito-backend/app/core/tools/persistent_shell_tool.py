import asyncio
import json
import os
import pty
import re
import signal
import uuid
from typing import Any, Dict, List, Optional
from app.core.tools.base import AgentTool, ToolContext, ToolResult
from app.core.exec_policy import default_exec_policy, session_approval_cache, ExecPolicy, SessionApprovalCache


def get_descendant_pids(parent_pid: int) -> List[int]:
    """
    Scans /proc to find all descendant child process PIDs of a given parent PID.
    Returns empty list if /proc is not available or readable.
    """
    ppid_map: Dict[int, List[int]] = {}
    try:
        if not os.path.exists("/proc"):
            return []
        for entry in os.listdir("/proc"):
            if entry.isdigit():
                pid = int(entry)
                try:
                    with open(f"/proc/{pid}/stat", "r") as f:
                        stat_content = f.read()
                        rparen = stat_content.rfind(")")
                        if rparen != -1:
                            parts = stat_content[rparen + 1 :].strip().split()
                            ppid = int(parts[1])
                            ppid_map.setdefault(ppid, []).append(pid)
                except (PermissionError, FileNotFoundError, ValueError, IndexError):
                    continue
    except Exception:
        pass

    descendants: List[int] = []
    stack = [parent_pid]
    while stack:
        curr = stack.pop()
        children = ppid_map.get(curr, [])
        for child in children:
            descendants.append(child)
            stack.append(child)
    return descendants


class PersistentShellSession:
    """
    Manages a single persistent PTY shell session.
    """

    def __init__(self, session_id: str, initial_cwd: str):
        self.session_id = session_id
        self.initial_cwd = initial_cwd
        self.master_fd: Optional[int] = None
        self.master_file: Optional[Any] = None
        self.process: Optional[asyncio.subprocess.Process] = None
        self.reader: Optional[asyncio.StreamReader] = None
        self.lock = asyncio.Lock()
        self._closed = False

    async def start(self) -> None:
        master_fd, slave_fd = pty.openpty()
        self.master_fd = master_fd

        env = os.environ.copy()
        env["TERM"] = "dumb"

        try:
            self.process = await asyncio.create_subprocess_exec(
                "/bin/bash",
                "--norc",
                "--noprofile",
                "-i",
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                start_new_session=True,
                cwd=self.initial_cwd,
                env=env,
            )
        finally:
            os.close(slave_fd)

        loop = asyncio.get_running_loop()
        self.reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(self.reader)
        self.master_file = os.fdopen(master_fd, "r+b", buffering=0)
        await loop.connect_read_pipe(lambda: protocol, self.master_file)

        # Disable echo and clear PS1 prompt
        self.master_file.write(b'export PS1=""; stty -echo 2>/dev/null || true\n')
        await asyncio.sleep(0.05)

    @property
    def pid(self) -> Optional[int]:
        return self.process.pid if self.process else None

    def get_cwd(self) -> str:
        if self.pid:
            try:
                proc_cwd = os.readlink(f"/proc/{self.pid}/cwd")
                if proc_cwd and os.path.exists(proc_cwd):
                    return proc_cwd
            except Exception:
                pass
        return self.initial_cwd

    def get_child_pids(self) -> List[int]:
        if not self.pid:
            return []
        return get_descendant_pids(self.pid)

    async def run_command(self, command: str, timeout_seconds: int) -> ToolResult:
        async with self.lock:
            if self._closed or not self.process or self.process.returncode is not None:
                return ToolResult(is_error=True, output="Error: Session is not active.")

            cmd_id = uuid.uuid4().hex[:8]
            sentinel_prefix = f"__CMD_END_{cmd_id}_"
            full_cmd = f"{command.strip()}\necho \"{sentinel_prefix}$?\"\n"

            try:
                self.master_file.write(full_cmd.encode("utf-8"))
            except Exception as e:
                return ToolResult(is_error=True, output=f"Error writing to session: {e}")

            out_buf = b""
            is_timeout = False
            exit_code = 0

            while True:
                try:
                    chunk = await asyncio.wait_for(
                        self.reader.read(1024), timeout=float(timeout_seconds)
                    )
                    if not chunk:
                        break
                    out_buf += chunk

                    if sentinel_prefix.encode("utf-8") in out_buf:
                        idx = out_buf.find(sentinel_prefix.encode("utf-8"))
                        rest = out_buf[idx + len(sentinel_prefix.encode("utf-8")) :]
                        if b"\n" in rest or b"\r" in rest:
                            code_str = (
                                rest.split(b"\r")[0]
                                .split(b"\n")[0]
                                .decode("utf-8", errors="ignore")
                            )
                            try:
                                exit_code = int(code_str)
                            except ValueError:
                                exit_code = 0
                            break
                except asyncio.TimeoutError:
                    is_timeout = True
                    try:
                        self.master_file.write(b"\x03")
                    except Exception:
                        pass
                    try:
                        c = await asyncio.wait_for(self.reader.read(1024), timeout=0.5)
                        out_buf += c
                    except asyncio.TimeoutError:
                        pass
                    break
                except Exception as e:
                    return ToolResult(is_error=True, output=f"Error reading session output: {e}")

            if is_timeout:
                return ToolResult(
                    is_error=True,
                    output=f"Error: Command timed out after {timeout_seconds} seconds.",
                )

            raw_str = out_buf.decode("utf-8", errors="replace")
            idx = raw_str.find(sentinel_prefix)
            if idx != -1:
                raw_str = raw_str[:idx]

            raw_str = raw_str.replace("\r\n", "\n").replace("\r", "\n")
            lines = [
                line
                for line in raw_str.split("\n")
                if line.strip()
                and not line.startswith("export PS1=")
                and not line.startswith("stty -echo")
            ]

            clean_output = "\n".join(lines).strip()
            return ToolResult(output=clean_output, is_error=(exit_code != 0))

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True

        shell_pid = self.pid
        child_pids = self.get_child_pids()

        for cpid in child_pids:
            try:
                os.kill(cpid, signal.SIGKILL)
            except Exception:
                pass

        if shell_pid:
            try:
                pgid = os.getpgid(shell_pid)
                os.killpg(pgid, signal.SIGKILL)
            except Exception:
                pass
            try:
                os.kill(shell_pid, signal.SIGKILL)
            except Exception:
                pass

        if self.process:
            try:
                await asyncio.wait_for(self.process.wait(), timeout=1.0)
            except Exception:
                pass

        if self.master_file:
            try:
                self.master_file.close()
            except Exception:
                pass


class PersistentShellSessionManager:
    """
    Registry for managing persistent shell sessions across tool calls.
    """

    def __init__(self):
        self._sessions: Dict[str, PersistentShellSession] = {}
        self._lock = asyncio.Lock()

    async def get_or_create_session(self, session_id: str, cwd: str) -> PersistentShellSession:
        async with self._lock:
            session = self._sessions.get(session_id)
            if session and not session._closed:
                if session.process and session.process.returncode is None:
                    return session
                else:
                    await session.close()
                    del self._sessions[session_id]

            new_session = PersistentShellSession(session_id=session_id, initial_cwd=cwd)
            await new_session.start()
            self._sessions[session_id] = new_session
            return new_session

    async def kill_session(self, session_id: str) -> bool:
        async with self._lock:
            session = self._sessions.pop(session_id, None)
            if session:
                await session.close()
                return True
            return False

    async def get_session(self, session_id: str) -> Optional[PersistentShellSession]:
        async with self._lock:
            return self._sessions.get(session_id)


_global_session_manager = PersistentShellSessionManager()


class PersistentShellTool(AgentTool):
    name = "persistent_shell"
    description = (
        "Execute commands in a persistent shell session maintaining working directory, "
        "environment variables, and background processes between calls."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": (
                    "The bash command to execute, or special management commands "
                    "'__get_state__' or '__kill__'."
                ),
            },
            "session_id": {
                "type": "string",
                "description": "Unique session identifier. Defaults to context session_id or task_id.",
            },
            "timeout_seconds": {
                "type": "integer",
                "description": "Command timeout in seconds.",
                "default": 30,
            },
        },
        "required": ["command"],
    }

    def __init__(
        self,
        manager: Optional[PersistentShellSessionManager] = None,
        exec_policy: ExecPolicy = default_exec_policy,
        approval_cache: SessionApprovalCache = session_approval_cache,
    ):
        super().__init__()
        self.manager = manager or _global_session_manager
        self.exec_policy = exec_policy
        self.approval_cache = approval_cache

    async def execute(self, arguments: Dict[str, Any], context: ToolContext) -> ToolResult:
        command = arguments.get("command")
        if not command:
            return ToolResult(is_error=True, output="Error: command is required.")

        session_id = (
            arguments.get("session_id")
            or getattr(context, "session_id", None)
            or getattr(context, "task_id", None)
            or "default_session"
        )
        timeout_seconds = min(int(arguments.get("timeout_seconds", 30)), 120)
        user_approved = bool(arguments.get("user_approved", False))

        # Internal management command: __get_state__
        if command.strip() == "__get_state__":
            session = await self.manager.get_session(session_id)
            if not session or session._closed:
                state_info = {
                    "session_id": session_id,
                    "is_active": False,
                    "cwd": context.cwd,
                    "shell_pid": None,
                    "child_pids": [],
                }
            else:
                state_info = {
                    "session_id": session_id,
                    "is_active": True,
                    "cwd": session.get_cwd(),
                    "shell_pid": session.pid,
                    "child_pids": session.get_child_pids(),
                }
            return ToolResult(output=json.dumps(state_info, indent=2))

        # Internal management command: __kill__
        if command.strip() == "__kill__":
            killed = await self.manager.kill_session(session_id)
            status = "Session terminated successfully." if killed else "Session not found or already closed."
            return ToolResult(output=status)

        from app.core.exec_policy import evaluate_command_execution, ExecVerdict
        verdict, reason = evaluate_command_execution(
            command=command,
            cwd=context.cwd,
            trusted=getattr(context, "trusted", False),
            session_id=session_id,
            user_approved=user_approved,
            exec_policy=self.exec_policy,
            approval_cache=self.approval_cache,
        )

        if verdict != ExecVerdict.PERMITIR:
            return ToolResult(is_error=True, output=f"Error: {reason}")

        try:
            session = await self.manager.get_or_create_session(
                session_id=session_id, cwd=context.cwd
            )
            return await session.run_command(command, timeout_seconds=timeout_seconds)
        except Exception as e:
            return ToolResult(is_error=True, output=f"Error in persistent shell execution: {str(e)}")
