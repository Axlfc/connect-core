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

SAFE_ENV_KEYS = ("PATH", "LANG", "LC_ALL", "TERM")


class SandboxUnavailableError(RuntimeError):
    """
    Exception raised when bubblewrap ('bwrap') or resource limiter ('prlimit')
    is not installed or available on the host system.
    """
    pass


class SandboxNetworkError(RuntimeError):
    """
    Exception raised when an outbound network connection attempt or target host check
    intercepted by Cognito main orchestrator targets a host or IP not in the allowed network whitelist.
    Note: Subprocesses executed inside bwrap sandbox have complete kernel network namespace isolation (--unshare-all)
    and cannot open any outbound sockets regardless of host whitelist.
    """
    pass


def is_bwrap_available() -> bool:
    """
    Checks if bubblewrap ('bwrap') binary is available on the host system.
    """
    return shutil.which("bwrap") is not None


def is_prlimit_available() -> bool:
    """
    Checks if prlimit binary is available on the host system.
    """
    return shutil.which("prlimit") is not None


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


def build_safe_env() -> Dict[str, str]:
    """
    Builds a sanitized environment dictionary containing only safe environment keys.
    Prevents leaking host secrets, credentials, and API tokens to sandboxed subprocesses.
    """
    safe_env = {}
    for key in SAFE_ENV_KEYS:
        if key in os.environ:
            safe_env[key] = os.environ[key]

    if "PATH" not in safe_env:
        safe_env["PATH"] = "/usr/local/bin:/usr/bin:/bin"

    return safe_env


def get_prlimit_prefix() -> List[str]:
    """
    Generates prlimit resource limitation arguments prefix.
    Configurable via environment variables:
    - COGNITO_SANDBOX_CPU_SECONDS (default: 30)
    - COGNITO_SANDBOX_MEMORY_MB (default: 2048)
    - COGNITO_SANDBOX_NPROC (default: 256)
    - COGNITO_SANDBOX_NOFILE (default: 1024)
    """
    if not is_prlimit_available():
        return []

    try:
        cpu_sec = int(os.getenv("COGNITO_SANDBOX_CPU_SECONDS", "30"))
    except ValueError:
        cpu_sec = 30

    try:
        mem_mb = int(os.getenv("COGNITO_SANDBOX_MEMORY_MB", "2048"))
    except ValueError:
        mem_mb = 2048
    mem_bytes = mem_mb * 1024 * 1024

    try:
        nproc = int(os.getenv("COGNITO_SANDBOX_NPROC", "256"))
    except ValueError:
        nproc = 256

    try:
        nofile = int(os.getenv("COGNITO_SANDBOX_NOFILE", "1024"))
    except ValueError:
        nofile = 1024

    return [
        "prlimit",
        f"--cpu={cpu_sec}",
        f"--as={mem_bytes}",
        f"--nproc={nproc}",
        f"--nofile={nofile}",
    ]


def get_sandbox_allowed_hosts() -> List[str]:
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
    if not text:
        return []

    hosts = set()

    url_pattern = re.compile(r'https?://([a-zA-Z0-9\.\-]+(?::\d+)?)')
    for match in url_pattern.findall(text):
        host = match.split(":")[0].lower()
        if host:
            hosts.add(host)

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
    - Clears environment (--clearenv --setenv PATH ...).
    - Hides user home directory (--tmpfs ~) before mounting CWD.
    - Re-exposes paths listed in COGNITO_SANDBOX_HOME_RO_PATHS as read-only if configured.
    - Mounts CWD with write permissions (--bind {cwd} {cwd}).
    - Unshares all namespaces including network namespace (--unshare-all --die-with-parent).
    """
    cwd_path = Path(cwd).resolve()
    cwd_str = str(cwd_path)

    path_val = os.getenv("PATH", "/usr/local/bin:/usr/bin:/bin")

    args = [
        "bwrap",
        "--clearenv",
        "--setenv", "PATH", path_val,
        "--setenv", "LANG", os.getenv("LANG", "C.UTF-8"),
        "--ro-bind", "/", "/",
        "--dev", "/dev",
        "--proc", "/proc",
        "--tmpfs", "/tmp",
    ]

    # Hide user home directory
    user_home = Path(os.path.expanduser("~")).resolve()
    user_home_str = str(user_home)
    args.extend(["--tmpfs", user_home_str])

    # Re-expose specific read-only paths under home if explicitly configured
    home_ro_paths = os.getenv("COGNITO_SANDBOX_HOME_RO_PATHS", "").strip()
    if home_ro_paths:
        for raw_p in home_ro_paths.split(","):
            p_str = raw_p.strip()
            if p_str:
                p_path = Path(p_str).resolve()
                if p_path.exists() and (p_path == user_home or user_home in p_path.parents):
                    args.extend(["--ro-bind", str(p_path), str(p_path)])

    # Ensure CWD parent directories exist and mount CWD writable
    args.extend([
        "--dir", cwd_str,
        "--bind", cwd_str, cwd_str,
        "--unshare-all",
        "--die-with-parent",
    ])

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
        Verifies that bubblewrap ('bwrap') and prlimit are available on host.
        If missing, logs a CRITICAL security error and raises SandboxUnavailableError.
        """
        if not is_bwrap_available():
            msg = (
                "Error de Seguridad: Bubblewrap (bwrap) no está instalado en el host. "
                "La ejecución de código no está aislada. Instala bwrap o contacta al administrador."
            )
            logger.critical(msg)
            raise SandboxUnavailableError(msg)

        if not is_prlimit_available() and not is_sandbox_disabled_dev_only():
            msg = (
                "Error de Seguridad: prlimit no está disponible en el host. "
                "No se pueden aplicar límites de recursos de CPU y memoria. Instala prlimit o utiliza COGNITO_DISABLE_SANDBOX_DEV_ONLY."
            )
            logger.critical(msg)
            raise SandboxUnavailableError(msg)

    def validate_destination_host(self, target: str) -> bool:
        return is_host_allowed(target, allowed_hosts=self.allowed_hosts)

    def _check_network_targets(self, text: str, target_host: Optional[str] = None) -> Optional[str]:
        hosts = extract_hosts_from_text(text)
        if target_host and target_host not in hosts:
            hosts.append(target_host)

        for h in hosts:
            if not self.validate_destination_host(h):
                return h
        return None

    def _resolve_target_host(self, text: str, explicit_target: Optional[str] = None) -> Optional[str]:
        extracted = extract_hosts_from_text(text)
        if extracted:
            return extracted[0]
        return explicit_target or self.target_host

    async def execute_cmd(
        self,
        command: str,
        session_id: str = "default_session",
        project_trusted: bool = False,
        user_approved: bool = False,
        target_host: Optional[str] = None
    ) -> Dict[str, Any]:
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
        host_to_pass = self._resolve_target_host(command, target_host)

        prlimit_prefix = get_prlimit_prefix()
        bwrap_cmd = build_bwrap_args(
            cwd=cwd_path,
            allowed_network=self.allowed_network,
            target_host=host_to_pass,
            allowed_hosts=self.allowed_hosts
        ) + ["sh", "-c", command]

        cmd = prlimit_prefix + bwrap_cmd if prlimit_prefix else bwrap_cmd
        safe_env = build_safe_env()

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd_path,
                env=safe_env,
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
                    await proc.wait()
                except Exception:
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

        host_to_pass = self._resolve_target_host(code, target_host)
        prlimit_prefix = get_prlimit_prefix()
        bwrap_cmd = build_bwrap_args(
            cwd=cwd_path,
            allowed_network=net_allowed,
            target_host=host_to_pass,
            allowed_hosts=self.allowed_hosts
        ) + [sys.executable, str(temp_file)]

        cmd = prlimit_prefix + bwrap_cmd if prlimit_prefix else bwrap_cmd
        safe_env = build_safe_env()
        context = "bwrap"

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd_path,
                env=safe_env,
            )

            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self.timeout)
                exit_code = proc.returncode
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                    await proc.wait()
                except Exception:
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
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass
