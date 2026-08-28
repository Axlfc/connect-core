import os
import tomllib
from pathlib import Path
from typing import Dict, Any, Optional

PROMPTS_DIR = Path(__file__).parent / "prompts"
DEFAULT_VERSION = "v1.1"

def load_system_prompt_config(version: str = DEFAULT_VERSION) -> Dict[str, Any]:
    norm_version = version if version.startswith("v") else f"v{version}"
    filename = f"system_prompt.{norm_version}.toml"
    path = PROMPTS_DIR / filename
    if not path.is_file():
        # Fallback if provided exact filename or version string without leading v
        alt_filename = f"system_prompt.{version}.toml"
        path = PROMPTS_DIR / alt_filename
        if not path.is_file():
            raise FileNotFoundError(f"System prompt file for version '{version}' not found at {path}")

    with open(path, "rb") as f:
        return tomllib.load(f)

def get_system_prompt(version: Optional[str] = None) -> str:
    v = version or os.getenv("COGNITO_SYSTEM_PROMPT_VERSION", DEFAULT_VERSION)
    config = load_system_prompt_config(v)
    return config["prompt"]

COGNITO_SYSTEM_PROMPT = get_system_prompt(DEFAULT_VERSION)

from app.core.resource_loader import ResourceLoader
from app.core.fact_memory import fact_memory_manager

def build_system_message(
    cwd: str,
    version: Optional[str] = None,
    user_id: Optional[str] = None,
    project_id: Optional[str] = None,
    org_id: Optional[str] = None,
) -> str:
    prompt_text = get_system_prompt(version)
    parts = [prompt_text]

    facts_block = fact_memory_manager.format_facts_for_prompt(user_id=user_id, project_id=project_id, org_id=org_id)
    if facts_block:
        parts.append(f"---\n\n{facts_block}")

    loader = ResourceLoader(cwd)
    agents_md = loader.discover_agents_md()
    if agents_md and agents_md.strip():
        parts.append(f"---\n\nContexto específico de este repositorio (AGENTS.md):\n\n{agents_md}")

    return "\n\n".join(parts)
