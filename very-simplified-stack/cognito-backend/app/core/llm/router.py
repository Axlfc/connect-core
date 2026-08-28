import logging
from pathlib import Path
from typing import AsyncIterator, Dict, Any, List, Optional, Union

from app.core.llm.adapters.base import (
    LLMAdapter,
    LLMError,
    get_provider_class,
)
import app.core.llm.adapters  # Ensures all adapter modules are imported and registered
from app.core.llm.config import RouterConfig, AdapterConfig, RouteConfig, load_config_from_file

logger = logging.getLogger(__name__)


def create_adapter_from_config(cfg: AdapterConfig) -> LLMAdapter:
    """Factory function to build LLMAdapter instances from AdapterConfig using dynamic provider lookup."""
    adapter_cls = get_provider_class(cfg.type)
    return adapter_cls(
        model_name=cfg.model_name,
        base_url=cfg.base_url,
        api_key=cfg.api_key,
        max_retries=cfg.max_retries,
        initial_backoff=cfg.initial_backoff,
        backoff_factor=cfg.backoff_factor,
        timeout=cfg.timeout,
    )


class LLMRouter:
    """
    LLM Router manages registered adapters and model routes.
    Selects the correct adapter strategy based on request route/model.
    Executes primary adapter and falls back to secondary adapters if primary fails.
    """

    def __init__(self):
        self._adapters: Dict[str, LLMAdapter] = {}
        self._routes: Dict[str, RouteConfig] = {}

    def register_adapter(self, adapter_id: str, adapter: LLMAdapter) -> None:
        """Registers an adapter instance with a unique ID."""
        self._adapters[adapter_id] = adapter
        logger.info(f"Registered LLM Adapter '{adapter_id}' ({adapter.__class__.__name__}) for model '{adapter.model_name}'")

    def register_route(
        self,
        route_name: str,
        primary_adapter_id: str,
        fallback_adapter_ids: Optional[List[str]] = None,
    ) -> None:
        """Registers a named route with primary and optional fallback adapters."""
        self._routes[route_name] = RouteConfig(
            primary_adapter_id=primary_adapter_id,
            fallback_adapter_ids=fallback_adapter_ids or [],
        )
        logger.info(f"Registered LLM Route '{route_name}' -> Primary: '{primary_adapter_id}', Fallbacks: {fallback_adapter_ids or []}")

    def load_from_config(self, config: RouterConfig) -> None:
        """Loads adapters and routes from a RouterConfig instance."""
        for adapter_cfg in config.adapters:
            adapter_instance = create_adapter_from_config(adapter_cfg)
            self.register_adapter(adapter_cfg.id, adapter_instance)

        for route_name, route_cfg in config.routes.items():
            self.register_route(
                route_name=route_name,
                primary_adapter_id=route_cfg.primary_adapter_id,
                fallback_adapter_ids=route_cfg.fallback_adapter_ids,
            )

    def load_from_file(self, config_path: Union[str, Path]) -> None:
        """Loads configuration from a JSON file path using pathlib.Path."""
        cfg = load_config_from_file(config_path)
        self.load_from_config(cfg)

    def get_adapter(self, adapter_id: str) -> Optional[LLMAdapter]:
        """Returns registered adapter by ID."""
        return self._adapters.get(adapter_id)

    def _resolve_adapter_chain(self, route_or_adapter_id: str) -> List[str]:
        """
        Resolves adapter chain for a given route name or direct adapter ID.
        Returns a list of adapter IDs starting with primary, followed by fallbacks.
        """
        if route_or_adapter_id in self._routes:
            route = self._routes[route_or_adapter_id]
            chain = [route.primary_adapter_id] + list(route.fallback_adapter_ids)
            return chain

        if route_or_adapter_id in self._adapters:
            return [route_or_adapter_id]

        raise LLMError(f"Route or Adapter ID '{route_or_adapter_id}' not found in LLMRouter")

    async def chat_completion(
        self,
        route_or_adapter_id: str,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Executes chat completion with automatic fallback across configured adapters.
        """
        chain = self._resolve_adapter_chain(route_or_adapter_id)
        last_exception: Optional[Exception] = None

        for idx, adapter_id in enumerate(chain):
            adapter = self.get_adapter(adapter_id)
            if not adapter:
                logger.error(f"Adapter '{adapter_id}' in chain for '{route_or_adapter_id}' is not registered.")
                continue

            try:
                if idx > 0:
                    logger.warning(
                        f"[LLMRouter] Falling back to adapter '{adapter_id}' (model: '{adapter.model_name}') "
                        f"for route '{route_or_adapter_id}'"
                    )
                return await adapter.chat_completion(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )
            except Exception as e:
                last_exception = e
                logger.warning(
                    f"[LLMRouter] Adapter '{adapter_id}' failed for route '{route_or_adapter_id}': {e}."
                )

        raise LLMError(
            f"All adapters in route '{route_or_adapter_id}' failed. Last error: {last_exception}"
        ) from last_exception

    async def stream_completion(
        self,
        route_or_adapter_id: str,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Executes stream completion with automatic fallback across configured adapters.
        """
        chain = self._resolve_adapter_chain(route_or_adapter_id)
        last_exception: Optional[Exception] = None

        for idx, adapter_id in enumerate(chain):
            adapter = self.get_adapter(adapter_id)
            if not adapter:
                logger.error(f"Adapter '{adapter_id}' in chain for '{route_or_adapter_id}' is not registered.")
                continue

            try:
                if idx > 0:
                    logger.warning(
                        f"[LLMRouter] Streaming fallback to adapter '{adapter_id}' (model: '{adapter.model_name}') "
                        f"for route '{route_or_adapter_id}'"
                    )
                stream = adapter.stream_completion(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )
                async for chunk in stream:
                    yield chunk
                return
            except Exception as e:
                last_exception = e
                logger.warning(
                    f"[LLMRouter] Adapter '{adapter_id}' stream failed for route '{route_or_adapter_id}': {e}."
                )

        raise LLMError(
            f"All adapters in stream route '{route_or_adapter_id}' failed. Last error: {last_exception}"
        ) from last_exception
