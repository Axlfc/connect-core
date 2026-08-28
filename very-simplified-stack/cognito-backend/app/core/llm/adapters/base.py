import asyncio
import logging
from abc import ABC, abstractmethod
from typing import AsyncIterator, Dict, Any, List, Optional, Union, Type, TypeVar, Callable

logger = logging.getLogger(__name__)

# Registry for dynamic LLM Provider registration
PROVIDER_REGISTRY: Dict[str, Type["LLMAdapter"]] = {}

TypeAdapter = TypeVar("TypeAdapter", bound=Type["LLMAdapter"])


def register_provider(*names: str) -> Callable[[TypeAdapter], TypeAdapter]:
    """
    Decorator to register an LLMAdapter class under one or more provider names.
    """
    def decorator(cls: TypeAdapter) -> TypeAdapter:
        for name in names:
            normalized = name.lower().strip()
            PROVIDER_REGISTRY[normalized] = cls
            logger.info(f"Registered LLM provider '{normalized}' -> {cls.__name__}")
        return cls
    return decorator


def get_provider_class(provider_name: str) -> Type["LLMAdapter"]:
    """
    Retrieves the adapter class registered for a given provider name.
    """
    normalized = provider_name.lower().strip()
    if normalized not in PROVIDER_REGISTRY:
        supported = list(PROVIDER_REGISTRY.keys())
        raise ValueError(
            f"Unsupported or unregistered LLM provider type: '{provider_name}'. "
            f"Registered providers: {supported}"
        )
    return PROVIDER_REGISTRY[normalized]


class LLMError(Exception):
    """Base exception for all LLM Adapter errors."""
    def __init__(self, message: str, status_code: Optional[int] = None, raw_response: Optional[Any] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.raw_response = raw_response


class LLMRetryableError(LLMError):
    """Exception for errors that can be retried (e.g. 503 Service Unavailable, 429 Rate Limit, timeouts)."""
    pass


class LLMNonRetryableError(LLMError):
    """Exception for non-retryable errors that must fail fast (e.g. 400 Bad Request, 401 Unauthorized, 403 Forbidden)."""
    pass


def is_retryable_http_status(status_code: int) -> bool:
    """
    Returns True if the HTTP status code is transient/retryable.
    HTTP 429 (Too Many Requests) and HTTP 5xx (Server Errors) are retryable.
    HTTP 4xx (Client Errors) except 429 are non-retryable and should fail fast.
    """
    if status_code == 429 or status_code >= 500:
        return True
    return False


class LLMAdapter(ABC):
    """
    Abstract Base Class for LLM Adapters.
    Implements the Strategy Pattern for interacting with various LLM providers (Ollama, OpenAI, DeepSeek, etc.).
    Provides automatic smart retries with exponential backoff for retryable errors.
    """

    def __init__(
        self,
        model_name: str,
        base_url: str,
        api_key: Optional[str] = None,
        max_retries: int = 3,
        initial_backoff: float = 1.0,
        backoff_factor: float = 2.0,
        timeout: float = 60.0,
    ):
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.backoff_factor = backoff_factor
        self.timeout = timeout

    @abstractmethod
    async def _do_chat_completion(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Concrete implementation for sending a chat completion request."""
        pass

    @abstractmethod
    async def _do_stream_completion(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Concrete implementation for streaming a chat completion request."""
        pass

    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Public chat_completion method with exponential backoff retry logic for retryable errors.
        Fails fast on non-retryable errors (e.g. 400 Format errors).
        """
        attempt = 0
        current_backoff = self.initial_backoff

        while True:
            try:
                attempt += 1
                return await self._do_chat_completion(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )
            except LLMNonRetryableError as e:
                logger.error(f"[{self.__class__.__name__}] Non-retryable error on model '{self.model_name}': {e}")
                raise e
            except (LLMRetryableError, Exception) as e:
                err = e if isinstance(e, LLMError) else LLMRetryableError(f"Unexpected error: {str(e)}")

                if attempt > self.max_retries:
                    logger.error(
                        f"[{self.__class__.__name__}] Retries exhausted ({self.max_retries}) for model '{self.model_name}'. Error: {err}"
                    )
                    raise err

                logger.warning(
                    f"[{self.__class__.__name__}] Attempt {attempt}/{self.max_retries} failed for model '{self.model_name}': {err}. "
                    f"Retrying in {current_backoff:.2f}s..."
                )
                await asyncio.sleep(current_backoff)
                current_backoff *= self.backoff_factor

    async def stream_completion(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Public stream_completion method with exponential backoff retry logic on connection/initialization.
        Fails fast on non-retryable errors.
        """
        attempt = 0
        current_backoff = self.initial_backoff

        while True:
            try:
                attempt += 1
                stream = self._do_stream_completion(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )
                async for chunk in stream:
                    yield chunk
                return
            except LLMNonRetryableError as e:
                logger.error(f"[{self.__class__.__name__}] Non-retryable stream error on model '{self.model_name}': {e}")
                raise e
            except (LLMRetryableError, Exception) as e:
                err = e if isinstance(e, LLMError) else LLMRetryableError(f"Stream error: {str(e)}")

                if attempt > self.max_retries:
                    logger.error(
                        f"[{self.__class__.__name__}] Stream retries exhausted ({self.max_retries}) for model '{self.model_name}'. Error: {err}"
                    )
                    raise err

                logger.warning(
                    f"[{self.__class__.__name__}] Stream attempt {attempt}/{self.max_retries} failed for model '{self.model_name}': {err}. "
                    f"Retrying in {current_backoff:.2f}s..."
                )
                await asyncio.sleep(current_backoff)
                current_backoff *= self.backoff_factor


# Alias for explicitly requested interface name
LLMProviderAdapter = LLMAdapter
