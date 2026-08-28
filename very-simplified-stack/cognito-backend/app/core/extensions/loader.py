import os
import sys
import json
import venv
import logging
import asyncio
import functools
import contextlib
import subprocess
import importlib.util
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.extensions.api import ExtensionAPI

logger = logging.getLogger("cognito.extensions.loader")


class PluginEnvironment:
    """Manages an isolated virtual environment and module context for a packaged plugin."""

    def __init__(
        self,
        plugin_dir: Path,
        dependencies: Optional[List[str]] = None,
        requirements_file: Optional[Path] = None,
    ):
        self.plugin_dir = plugin_dir.resolve()
        self.dependencies = dependencies or []
        self.requirements_file = requirements_file

        self.venv_dir = self.plugin_dir / ".venv"
        try:
            self.venv_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            safe_name = "".join(c if c.isalnum() else "_" for c in self.plugin_dir.name)
            self.venv_dir = Path.home() / ".cognito" / "plugin_venvs" / safe_name
            self.venv_dir.mkdir(parents=True, exist_ok=True)

        self._ensure_venv_and_deps()
        self.site_packages = self._find_site_packages()
        self.modules: Dict[str, Any] = {}

    def _ensure_venv_and_deps(self) -> None:
        py_bin = self._get_python_bin()
        if not py_bin.exists():
            venv.create(self.venv_dir, with_pip=True)

        if not py_bin.exists():
            raise RuntimeError(f"Failed to create virtual environment at {self.venv_dir}")

        if self.dependencies:
            cmd = [str(py_bin), "-m", "pip", "install", *self.dependencies]
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if self.requirements_file and self.requirements_file.is_file():
            cmd = [str(py_bin), "-m", "pip", "install", "-r", str(self.requirements_file)]
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def _get_python_bin(self) -> Path:
        if sys.platform == "win32":
            return self.venv_dir / "Scripts" / "python.exe"
        return self.venv_dir / "bin" / "python"

    def _find_site_packages(self) -> List[str]:
        sp_dirs = []
        lib_dir = self.venv_dir / "lib"
        if lib_dir.exists():
            for p in lib_dir.glob("python*/site-packages"):
                if p.is_dir():
                    sp_dirs.append(str(p.resolve()))
        win_sp = self.venv_dir / "Lib" / "site-packages"
        if win_sp.is_dir():
            sp_dirs.append(str(win_sp.resolve()))

        if str(self.plugin_dir) not in sp_dirs:
            sp_dirs.insert(0, str(self.plugin_dir))

        return sp_dirs

    @contextlib.contextmanager
    def activate(self):
        orig_path = list(sys.path)
        orig_modules = dict(sys.modules)

        for path in reversed(self.site_packages):
            if path not in sys.path:
                sys.path.insert(0, path)

        sys.modules.update(self.modules)

        try:
            yield
        finally:
            for k, v in list(sys.modules.items()):
                if k not in orig_modules or sys.modules[k] != orig_modules[k]:
                    self.modules[k] = sys.modules[k]

            sys.modules.clear()
            sys.modules.update(orig_modules)
            sys.path[:] = orig_path

    def wrap_callable(self, fn: Optional[Callable]) -> Optional[Callable]:
        if fn is None:
            return None
        if asyncio.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def async_wrapper(*args, **kwargs):
                with self.activate():
                    return await fn(*args, **kwargs)
            return async_wrapper
        else:
            @functools.wraps(fn)
            def sync_wrapper(*args, **kwargs):
                with self.activate():
                    return fn(*args, **kwargs)
            return sync_wrapper

    def wrap_tool(self, tool: Any) -> Any:
        if hasattr(tool, "execute") and callable(getattr(tool, "execute")):
            tool.execute = self.wrap_callable(tool.execute)
        return tool


class IsolatedExtensionAPI:
    """Proxies ExtensionAPI calls to wrap tools and event handlers with a plugin's PluginEnvironment."""

    def __init__(self, api: "ExtensionAPI", env: PluginEnvironment):
        self._api = api
        self._env = env

    def register_tool(self, tool: Any) -> None:
        wrapped_tool = self._env.wrap_tool(tool)
        self._api.register_tool(wrapped_tool)

    def register_backend(self, config: Any) -> None:
        self._api.register_backend(config)

    def register_intent(self, intent: str, backend_name: str, model: str) -> None:
        self._api.register_intent(intent, backend_name, model)

    def on(self, event: str, handler: Callable) -> None:
        wrapped_handler = self._env.wrap_callable(handler)
        self._api.on(event, wrapped_handler)

    def on_agent_start(self, handler: Callable) -> None:
        self.on("on_agent_start", handler)

    def on_tool_pre_exec(self, handler: Callable) -> None:
        self.on("on_tool_pre_exec", handler)

    def on_tool_post_exec(self, handler: Callable) -> None:
        self.on("on_tool_post_exec", handler)

    def on_pre_compact(self, handler: Callable) -> None:
        self.on("on_pre_compact", handler)

    def __getattr__(self, item: str) -> Any:
        return getattr(self._api, item)


def _is_plugin_package_dir(p: Path) -> bool:
    if not p.is_dir() or p.name.startswith("."):
        return False
    if (p / "plugin.json").is_file() or (p / "manifest.json").is_file():
        return True
    if (p / "main.py").is_file() or (p / "plugin.py").is_file():
        return True
    return False


def discover_global() -> List[Path]:
    ext_dir = Path.home() / ".cognito" / "extensions"
    if not ext_dir.exists():
        return []

    discovered = []
    for p in sorted(ext_dir.iterdir()):
        if p.is_file() and p.suffix == ".py":
            discovered.append(p)
        elif _is_plugin_package_dir(p):
            discovered.append(p)
    return discovered


def discover_configured() -> List[Path]:
    config_path = Path.home() / ".cognito" / "config.json"
    if not config_path.exists():
        return []

    try:
        with open(config_path, "r") as f:
            config = json.load(f)
            paths = config.get("ExtensionPaths", [])

            discovered = []
            for p_str in paths:
                p = Path(p_str).expanduser().resolve()
                if p.is_file() and p.suffix == ".py":
                    discovered.append(p)
                elif _is_plugin_package_dir(p):
                    discovered.append(p)
                elif p.is_dir():
                    for item in sorted(p.iterdir()):
                        if item.is_file() and item.suffix == ".py":
                            discovered.append(item)
                        elif _is_plugin_package_dir(item):
                            discovered.append(item)
            return discovered
    except Exception as e:
        logger.warning(f"Failed to load ExtensionPaths from config.json: {e}")
        return []


def discover_project_local(cwd: str) -> List[Path]:
    ext_dir = Path(cwd) / ".cognito" / "extensions"
    if not ext_dir.exists():
        return []

    discovered = []
    for p in sorted(ext_dir.iterdir()):
        if p.is_file() and p.suffix == ".py":
            discovered.append(p)
        elif _is_plugin_package_dir(p):
            discovered.append(p)
    return discovered


def load_extension_package(path: Path, api: "ExtensionAPI") -> None:
    try:
        path = path.resolve()
        manifest = {}
        manifest_file = None
        if (path / "plugin.json").is_file():
            manifest_file = path / "plugin.json"
        elif (path / "manifest.json").is_file():
            manifest_file = path / "manifest.json"

        if manifest_file:
            try:
                with open(manifest_file, "r") as f:
                    manifest = json.load(f)
            except Exception as me:
                logger.warning(f"Failed to parse manifest at {manifest_file}: {me}")

        entrypoint = manifest.get("entrypoint") or manifest.get("main")
        dependencies = manifest.get("dependencies") or manifest.get("requirements") or []
        if isinstance(dependencies, str):
            dependencies = [dependencies]

        req_file = path / "requirements.txt"
        requirements_file = req_file if req_file.is_file() else None

        if entrypoint:
            entrypoint_path = path / entrypoint
        elif (path / "main.py").is_file():
            entrypoint_path = path / "main.py"
        elif (path / "plugin.py").is_file():
            entrypoint_path = path / "plugin.py"
        else:
            py_files = sorted([f for f in path.glob("*.py") if not f.name.startswith(".")])
            if not py_files:
                logger.warning(f"No Python entrypoint found in plugin package at {path}")
                return
            entrypoint_path = py_files[0]

        env = PluginEnvironment(
            plugin_dir=path,
            dependencies=dependencies,
            requirements_file=requirements_file,
        )
        iso_api = IsolatedExtensionAPI(api, env)

        module_name = f"cognito.plugins.{path.name}"
        with env.activate():
            spec = importlib.util.spec_from_file_location(module_name, entrypoint_path)
            if spec is None or spec.loader is None:
                logger.warning(f"Could not load spec for plugin package at {path}")
                return

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            if hasattr(module, "register"):
                module.register(iso_api)
                logger.info(f"Successfully registered plugin package: {path}")
            else:
                logger.warning(f"Plugin package at {path} has no register() function")

    except Exception as e:
        logger.warning(f"Failed to load plugin package at {path}: {e}", exc_info=True)


def load_extension_file(path: Path, api: "ExtensionAPI") -> None:
    if path.is_dir():
        load_extension_package(path, api)
        return

    try:
        module_name = f"cognito.extensions.{path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            logger.warning(f"Could not load spec for extension at {path}")
            return

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        if hasattr(module, "register"):
            module.register(api)
            logger.info(f"Successfully registered extension: {path}")
        else:
            logger.warning(f"Extension at {path} has no register() function")

    except Exception as e:
        logger.warning(f"Failed to load extension at {path}: {e}", exc_info=True)
