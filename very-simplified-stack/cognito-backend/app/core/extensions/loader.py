import os
import json
import logging
import importlib.util
from pathlib import Path
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.extensions.api import ExtensionAPI

logger = logging.getLogger("cognito.extensions.loader")

def discover_global() -> List[Path]:
    ext_dir = Path.home() / ".cognito" / "extensions"
    if not ext_dir.exists():
        return []
    return sorted([p for p in ext_dir.glob("*.py") if p.is_file()])

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
                elif p.is_dir():
                    discovered.extend(sorted([f for f in p.glob("*.py") if f.is_file()]))
            return discovered
    except Exception as e:
        logger.warning(f"Failed to load ExtensionPaths from config.json: {e}")
        return []

def discover_project_local(cwd: str) -> List[Path]:
    ext_dir = Path(cwd) / ".cognito" / "extensions"
    if not ext_dir.exists():
        return []
    return sorted([p for p in ext_dir.glob("*.py") if p.is_file()])

def load_extension_file(path: Path, api: "ExtensionAPI") -> None:
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
