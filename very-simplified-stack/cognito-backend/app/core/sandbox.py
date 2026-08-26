import asyncio
import os
import sys
import re
import shutil
import tempfile
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse
from app.core.exec_policy import default_exec_policy, session_approval_cache, ExecPolicy, SessionApprovalCache

logger = logging.getLogger(__name__)


class SandboxUnavailableError(RuntimeError):
    """
    Exception raised when bubblewrap ('bwrap') is not installed or available on the host system.
    """
    pass


class SandboxNetworkError(RuntimeError):
    """
    Exception raised when an outbound network connection attempt inside the sandbox
    targets a host or IP that is not in the allowed network whitelist.
    """
    pass


def is_bwrap_available() -> bool:
    """
    Checks if bubblewrap ('bwrap') binary is available on the host system.
    """
    return shutil.which("bwrap") is not None


def is_sandbox_disabled_dev_only() -> bool:
    """
    Checks if sandbox is explicitly disabled via COGNITO_DISABLE_SANDBOX_DEV_ONLY env var.
    This mode is intended strictly for local development.
    """
    disabled = os.getenv("COGNITO_DISABLE_SANDBOX_DEV_ONLY", "").strip().lower() in ("true", "1", "yes")
    if disabled:
        logger.warning(
            "⚠️ ATENCIÓN: El sandbox de Bubblewrap (bwrap) está DESACTIVADO por la variable de entorno "
            "COGNITO_DISABLE_SANDBOX_DEV_ONLY. Los comandos se ejecutarán directamente en el host sin aislamiento. "
            "USAR ÚNICAMENTE EN DESARROLLO LOCAL."
        )
    return disabled


def get_sandbox_allowed_hosts() -> List[str]:
    """
    Retrieves the whitelist of hosts/IPs permitted for outbound network access from the sandbox.
    By default, includes:
    1. Localhost and standard loopback addresses ("localhost", "127.0.0.1", "::1", "host.docker.internal").
    2. Hosts of active LLM backends configured in BackendRouter / BACKENDS_BY_PRIORITY.
    3. Hosts configured via environment variables (OPENAI_BASE_URL, OLLAMA_HOST, COGNITO_WORKER_URL).
    4. Custom operator-defined hosts provided in COGNITO_SANDBOX_ALLOWED_HOSTS (comma-separated).
    """
    allowed_hosts = {"localhost", "127.0.0.1", "::1", "host.docker.internal"}

    # 1. Collect LLM endpoints from BackendRouter / BACKENDS_BY_PRIORITY
    try:
        from app.services.backend_registry import BACKENDS_BY_PRIORITY
        for backend in BACKENDS_BY_PRIORITY:
            if backend.enabled and backend.base_url:
                parsed = urlparse(backend.base_url)
                if parsed.hostname:
                    allowed_hosts.add(parsed.hostname.lower())
    except Exception as e:
        logger.debug("Failed to extract LLM backend endpoints for sandbox whitelist: %s", e)

    # 2. Check standard environment variable endpoints
    for env_var in ("OPENAI_BASE_URL", "OLLAMA_HOST", "COGNITO_WORKER_URL"):
        val = os.getenv(env_var, "").strip()
        if val:
            if not val.startswith(("http://", "https://")):
                val = f"http://{val}"
            parsed = urlparse(val)
            if parsed.hostname:
                allowed_hosts.add(parsed.hostname.lower())

    # 3. Custom operator whitelist via COGNITO_SANDBOX_ALLOWED_HOSTS
    custom_hosts = os.getenv("COGNITO_SANDBOX_ALLOWED_HOSTS", "").strip()
    if custom_hosts:
        for host in custom_hosts.split(","):
            host_clean = host.strip()
            if host_clean:
                if "://" in host_clean:
                    parsed = urlparse(host_clean)
                    if parsed.hostname:
                        allowed_hosts.add(parsed.hostname.lower())
                else:
                    h = host_clean.split(":")[0].strip().lower()
                    if h:
                        allowed_hosts.add(h)

    return sorted(list(allowed_hosts))


def is_host_allowed(target: str, allowed_hosts: Optional[List[str]] = None) -> bool:
    """
    Checks if a target host, IP, domain, or URL is in the allowed sandbox whitelist.
    """
    if not target:
        return False

    target_clean = target.strip()
    hostname = target_clean

    if "://" in target_clean:
        parsed = urlparse(target_clean)
        hostname = parsed.hostname or target_clean
    elif ":" in target_clean:
        hostname = target_clean.split(":")[0]

    hostname = hostname.lower()
    whitelist = allowed_hosts if allowed_hosts is not None else get_sandbox_allowed_hosts()
    return hostname in [h.lower() for h in whitelist]


def extract_hosts_from_text(text: str) -> List[str]:
    """
    Extracts hostnames, domains, IP addresses, and URLs from a command string or Python code.
    """
    if not text:
        return []

    hosts = set()

    # 1. Match HTTP/HTTPS URLs
    url_pattern = re.compile(r'https?://([a-zA-Z0-9\.\-]+(?::\d+)?)')
    for match in url_pattern.findall(text):
        host = match.split(":")[0].lower()
        if host:
            hosts.add(host)

    # 2. Match IPv4 addresses
    ip_pattern = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')
    for ip in ip_pattern.findall(text):
        hosts.add(ip)

    return sorted(list(hosts))


def build_bwrap_args(
    cwd: Path,
    allowed_network: bool = False,
    target_host: Optional[str] = None,
    allowed_hosts: Optional[List[str]] = None
) -> List[str]:
    """
    Builds bubblewrap execution arguments for sandbox isolation.
    - Mounts root filesystem as read-only (--ro-bind / /).
    - Mounts essential virtual filesystems (--dev /dev --proc /proc --tmpfs /tmp).
    - Ensures parent directories of cwd exist inside the sandbox (--dir {cwd}).
    - Mounts working directory with write permissions (--bind {cwd} {cwd}).
    - Unshares all namespaces for process isolation (--unshare-all --die-with-parent).
    - Deny-all network policy by default (isolated network namespace, no --share-net).
    - Conditionally enables --share-net ONLY IF network is explicitly requested AND target_host is whitelisted.
    """
    cwd_path = Path(cwd).resolve()
    cwd_str = str(cwd_path)

    args = [
        "bwrap",
        "--ro-bind", "/", "/",
        "--dev", "/dev",
        "--proc", "/proc",
        "--tmpfs", "/tmp",
        "--dir", cwd_str,
        "--bind", cwd_str, cwd_str,
        "--unshare-all",
        "--die-with-parent"
    ]

    if allowed_network and target_host:
        if is_host_allowed(target_host, allowed_hosts=allowed_hosts):
            args.append("--share-net")
        else:
            logger.warning(
                "Network requested in sandbox for unwhitelisted host '%s'. "
                "Enforcing deny-all policy (no --share-net).", target_host
            )

    return args


class SandboxedExecutor:
    """
    Isolates code/shell execution in a safe, monitored python process (NOOA-11).
    Applies ExecPolicy evaluation, approval caching, timeouts, path restrictions, and network whitelisting.
    """
    def __init__(
        self,
        working_dir: Optional[str] = None,
        timeout: int = 30,
        allowed_network: bool = False,
        target_host: Optional[str] = None,
        allowed_hosts: Optional[List[str]] = None,
        exec_policy: ExecPolicy = default_exec_policy,
        approval_cache: SessionApprovalCache = session_approval_cache
    ):
        self.working_dir = working_dir or tempfile.gettempdir()
        self.timeout = timeout
        self.allowed_network = allowed_network
        self.target_host = target_host
        self.allowed_hosts = allowed_hosts
        self.exec_policy = exec_policy
        self.approval_cache = approval_cache

    async def _verify_bwrap(self) -> None:
        """
        Verifies that bubblewrap ('bwrap') is available. If not, logs a CRITICAL security error
        and raises SandboxUnavailableError.
        """
        if not is_bwrap_available():
            msg = (
                "Error de Seguridad: Bubblewrap (bwrap) no está instalado en el host. "
                "La ejecución de código no está aislada. Instala bwrap o contacta al administrador."
            )
            logger.critical(msg)
            raise SandboxUnavailableError(msg)

    def validate_destination_host(self, target: str) -> bool:
        """
        Validates whether a target network host is in the allowed whitelist.
        """
        return is_host_allowed(target, allowed_hosts=self.allowed_hosts)

    def _check_network_targets(self, text: str, target_host: Optional[str] = None) -> Optional[str]:
        """
        Scans text (command or code) for network targets and verifies all targets against the whitelist.
        Returns the first invalid host if any, otherwise returns None.
        """
        hosts = extract_hosts_from_text(text)
        if target_host and target_host not in hosts:
            hosts.append(target_host)

        for h in hosts:
            if not self.validate_destination_host(h):
                return h
        return None

    async def execute_cmd(
        self,
        command: str,
        session_id: str = "default_session",
        project_trusted: bool = False,
        user_approved: bool = False,
        target_host: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Evaluates ExecPolicy, session cache, and egress network policy before executing a command inside sandbox.
        Requires bwrap to be installed; raises SandboxUnavailableError if missing.
        Enforces destination host whitelist on all network targets in command.
        """
        await self._verify_bwrap()

        invalid_host = self._check_network_targets(command, target_host=target_host or self.target_host)
        if invalid_host:
            msg = f"Acceso de red denegado: El host '{invalid_host}' no está en la lista blanca del sandbox."
            logger.error(msg)
            raise SandboxNetworkError(msg)

        from app.core.exec_policy import evaluate_command_execution, ExecVerdict
        verdict, reason = evaluate_command_execution(
            command=command,
            cwd=self.working_dir,
            trusted=project_trusted,
            session_id=session_id,
            user_approved=user_approved,
            exec_policy=self.exec_policy,
            approval_cache=self.approval_cache,
        )

        if verdict != ExecVerdict.PERMITIR:
            return {
                "stdout": "",
                "stderr": reason,
                "exit_code": 1,
                "timed_out": False,
                "approval_required": True
            }

        cwd_path = Path(self.working_dir).resolve()
        host_to_pass = (extract_hosts_from_text(command) or [self.target_host])[0] if extract_hosts_from_text(command) else self.target_host
        cmd = build_bwrap_args(
            cwd=cwd_path,
            allowed_network=self.allowed_network,
            target_host=host_to_pass,
            allowed_hosts=self.allowed_hosts
        ) + ["sh", "-c", command]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd_path
            )

            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self.timeout)
                return {
                    "stdout": stdout.decode("utf-8", errors="replace"),
                    "stderr": stderr.decode("utf-8", errors="replace"),
                    "exit_code": proc.returncode,
                    "timed_out": False,
                    "approval_required": False
                }
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
                return {
                    "stdout": "",
                    "stderr": "Execution timed out.",
                    "exit_code": -1,
                    "timed_out": True,
                    "approval_required": False
                }

        except SandboxUnavailableError:
            raise
        except SandboxNetworkError:
            raise
        except Exception as e:
            return {
                "stdout": "",
                "stderr": f"Execution error: {str(e)}",
                "exit_code": 1,
                "timed_out": False,
                "approval_required": False
            }

    async def execute_code(
        self,
        code: str,
        allowed_network: Optional[bool] = None,
        target_host: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes raw Python code inside a separate python subprocess wrapped in bubblewrap (bwrap).
        Requires bwrap to be installed; raises SandboxUnavailableError if missing.
        Enforces destination host whitelist on all network targets in Python code.
        """
        await self._verify_bwrap()

        invalid_host = self._check_network_targets(code, target_host=target_host or self.target_host)
        if invalid_host:
            msg = f"Acceso de red denegado: El host '{invalid_host}' no está en la lista blanca del sandbox."
            logger.error(msg)
            raise SandboxNetworkError(msg)

        net_allowed = self.allowed_network if allowed_network is None else allowed_network
        cwd_path = Path(self.working_dir).resolve()

        # Save temporary file inside our safe working directory
        temp_file = cwd_path / f"sandbox_{os.getpid()}_{id(code)}.py"
        temp_file.write_text(code, encoding="utf-8")

        host_to_pass = (extract_hosts_from_text(code) or [self.target_host])[0] if extract_hosts_from_text(code) else self.target_host
        cmd = build_bwrap_args(
            cwd=cwd_path,
            allowed_network=net_allowed,
            target_host=host_to_pass,
            allowed_hosts=self.allowed_hosts
        ) + [sys.executable, str(temp_file)]
        context = "bwrap"

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd_path
            )

            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self.timeout)
                exit_code = proc.returncode
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
                return {
                    "stdout": "",
                    "stderr": "Execution timed out.",
                    "exit_code": -1,
                    "timed_out": True,
                    "context": context
                }

            return {
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
                "exit_code": exit_code,
                "timed_out": False,
                "context": context
            }

        finally:
            # Cleanup temp file
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass
