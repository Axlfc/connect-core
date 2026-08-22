import json
from pathlib import Path
from typing import Dict, List, Optional, Union
from pydantic import BaseModel, Field


class AdapterConfig(BaseModel):
    """Configuration for an individual LLM Adapter."""
    id: str
    type: str  # "ollama" or "openai_compatible"
    model_name: str
    base_url: str
    api_key: Optional[str] = None
    max_retries: int = 3
    initial_backoff: float = 1.0
    backoff_factor: float = 2.0
    timeout: float = 60.0


class RouteConfig(BaseModel):
    """Configuration for a model route specifying primary and fallback adapters."""
    primary_adapter_id: str
    fallback_adapter_ids: List[str] = Field(default_factory=list)


class RouterConfig(BaseModel):
    """Overall router configuration containing adapters and named routes."""
    adapters: List[AdapterConfig] = Field(default_factory=list)
    routes: Dict[str, RouteConfig] = Field(default_factory=dict)


def load_config_from_file(config_path: Union[str, Path]) -> RouterConfig:
    """
    Loads RouterConfig from a JSON file path using pathlib.Path.
    """
    path = Path(config_path) if isinstance(config_path, str) else config_path
    if not path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    content = path.read_text(encoding="utf-8")
    raw_data = json.loads(content)
    return RouterConfig.model_validate(raw_data)
