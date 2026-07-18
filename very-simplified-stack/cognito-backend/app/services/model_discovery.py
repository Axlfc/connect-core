import httpx
import logging
import time
from typing import List, Dict, Any, Optional
from app.models.domain import ModelDescriptor
from app.services.backend_registry import BACKENDS_BY_PRIORITY

logger = logging.getLogger("cognito.services.model_discovery")

class ModelDiscoveryService:
    def __init__(self):
        self._cached_catalog: Dict[str, ModelDescriptor] = {}
        self._last_discovery_time: float = 0
        self._cache_duration_sec: float = 300  # 5 minutes cache

    async def discover_ollama_models(self) -> List[ModelDescriptor]:
        # Find first ollama backend base_url
        ollama_url = "http://localhost:11434"
        for config in BACKENDS_BY_PRIORITY:
            if config.backend_type.value == "ollama":
                ollama_url = config.base_url
                break

        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{ollama_url}/api/tags")
                if resp.status_code == 200:
                    data = resp.json()
                    descriptors = []
                    for m in data.get("models", []):
                        name = m["name"]
                        # Capabilities heuristics
                        caps = ["generation"]
                        if "coder" in name or "qwen" in name:
                            caps.append("coding")
                        if "llava" in name or "vision" in name:
                            caps.append("vision")
                        if "embed" in name:
                            caps = ["embedding"]

                        descriptors.append(ModelDescriptor(
                            model_identifier=name,
                            display_name=name.split(":")[0].title(),
                            executor="Ollama",
                            supported_input_modalities=["text"] + (["image"] if "vision" in caps else []),
                            capabilities=caps,
                            is_available=True,
                            discovery_timestamp=time.time()
                        ))
                    return descriptors
        except Exception as e:
            logger.warning(f"Failed to discover Ollama models from {ollama_url}: {e}")
        return []

    async def get_combined_catalog(self, worker_discovered_models: Optional[List[ModelDescriptor]] = None) -> List[ModelDescriptor]:
        # Fetch Ollama
        ollama_models = await self.discover_ollama_models()

        # Merge with worker discovered Codex models
        catalog = {m.model_identifier: m for m in ollama_models}

        if worker_discovered_models:
            for m in worker_discovered_models:
                catalog[m.model_identifier] = m
        else:
            # Add logical fallback models for Codex
            fallback_codex = [
                ModelDescriptor(
                    model_identifier="codex.economy",
                    display_name="Codex Luna (Economy)",
                    executor="Codex",
                    supported_reasoning_efforts=["low"],
                    is_available=False,
                    capabilities=["coding", "generation"]
                ),
                ModelDescriptor(
                    model_identifier="codex.balanced",
                    display_name="Codex Terra (Balanced)",
                    executor="Codex",
                    supported_reasoning_efforts=["low", "medium"],
                    is_available=False,
                    capabilities=["coding", "generation"]
                ),
                ModelDescriptor(
                    model_identifier="codex.max",
                    display_name="Codex Sol (Max)",
                    executor="Codex",
                    supported_reasoning_efforts=["low", "medium", "high"],
                    is_available=False,
                    capabilities=["coding", "generation"]
                )
            ]
            for m in fallback_codex:
                if m.model_identifier not in catalog:
                    catalog[m.model_identifier] = m

        return list(catalog.values())

model_discovery_service = ModelDiscoveryService()
