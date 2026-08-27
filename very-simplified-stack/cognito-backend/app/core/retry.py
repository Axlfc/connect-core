import hashlib
import inspect
import logging
import uuid
from typing import Callable, Any, AsyncGenerator, Optional, Dict
import httpx
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

# Global in-memory store for idempotency key execution records
_IDEMPOTENCY_STORE: Dict[str, Any] = {}


def generate_idempotency_key(prefix: str = "op") -> str:
    """
    Generates a unique standard idempotency key using uuid and hashlib.
    """
    raw_id = f"{prefix}-{uuid.uuid4().hex}"
    digest = hashlib.sha256(raw_id.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def get_idempotency_store() -> Dict[str, Any]:
    """
    Returns the idempotency execution store (useful for inspection/testing).
    """
    return _IDEMPOTENCY_STORE


def record_idempotency_result(key: str, result: Any) -> None:
    """
    Records an execution result associated with an idempotency key.
    Useful when a side effect completes before a transient network failure occurs.
    """
    _IDEMPOTENCY_STORE[key] = result


def clear_idempotency_store() -> None:
    """
    Clears the idempotency execution store.
    """
    _IDEMPOTENCY_STORE.clear()

TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}

def is_transient_error(exc: Exception) -> bool:
    """
    Returns True if exception is a transient network or server error:
    - HTTP 429 (Rate Limit)
    - HTTP 500, 502, 503, 504 (Server Errors)
    - httpx.RequestError (Timeouts, connection errors, network drops)
    - Standard TimeoutError or ConnectionError
    """
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in TRANSIENT_STATUS_CODES
    if isinstance(exc, (httpx.RequestError, TimeoutError, ConnectionError)):
        return True
    return False

def get_transient_retrier(max_attempts: int = 3, min_wait: float = 0.5, max_wait: float = 4.0) -> AsyncRetrying:
    """
    Returns an AsyncRetrying instance configured for transient backoff.
    """
    return AsyncRetrying(
        retry=retry_if_exception(is_transient_error),
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(min=min_wait, max=max_wait),
        reraise=True,
        before_sleep=lambda retry_state: logger.warning(
            "[RetryBackoff] Transient error encountered (%s). Retrying attempt %d/%d...",
            retry_state.outcome.exception() if retry_state.outcome else "Unknown",
            retry_state.attempt_number,
            max_attempts,
        )
    )

async def retry_transient_async(
    async_func: Callable[..., Any],
    *args: Any,
    max_attempts: int = 3,
    min_wait: float = 0.5,
    max_wait: float = 4.0,
    idempotency_key: Optional[str] = None,
    is_destructive: bool = False,
    is_read_only: bool = False,
    idempotency_check: Optional[Callable[[str], Any]] = None,
    **kwargs: Any
) -> Any:
    """
    Executes an async function with transient retries using exponential backoff.
    Supports idempotency keys to prevent re-executing non-idempotent operations
    (is_destructive=True or is_read_only=False) if the operation already had effect.
    """
    non_idempotent = is_destructive or (not is_read_only)
    if non_idempotent and not idempotency_key:
        idempotency_key = generate_idempotency_key(prefix="tool-op")

    retrier = get_transient_retrier(max_attempts=max_attempts, min_wait=min_wait, max_wait=max_wait)
    async for attempt in retrier:
        with attempt:
            # Check before re-attempting if the operation with this key already took effect
            if idempotency_key:
                if idempotency_check is not None:
                    cached_res = idempotency_check(idempotency_key)
                    if cached_res is not None:
                        logger.info(
                            f"[Idempotency] Custom check found recorded execution for key {idempotency_key}. Skipping re-execution."
                        )
                        return cached_res
                elif idempotency_key in _IDEMPOTENCY_STORE:
                    logger.info(
                        f"[Idempotency] Key {idempotency_key} already executed successfully. Returning recorded result."
                    )
                    return _IDEMPOTENCY_STORE[idempotency_key]

            res = await async_func(*args, **kwargs)

            if idempotency_key:
                _IDEMPOTENCY_STORE[idempotency_key] = res

            return res

async def retry_transient_stream(
    generator_func: Callable[..., Any],
    *args: Any,
    max_attempts: int = 3,
    min_wait: float = 0.5,
    max_wait: float = 4.0,
    **kwargs: Any
) -> AsyncGenerator[Any, None]:
    """
    Executes an async generator function with transient retries.
    If a transient error occurs before yielding or during stream setup,
    it retries up to `max_attempts` with exponential backoff.
    """
    retrier = get_transient_retrier(max_attempts=max_attempts, min_wait=min_wait, max_wait=max_wait)

    async for attempt in retrier:
        with attempt:
            res = generator_func(*args, **kwargs)
            if inspect.iscoroutine(res):
                res = await res
            if hasattr(res, "__aiter__"):
                async for item in res:
                    yield item
            elif hasattr(res, "__iter__"):
                for item in res:
                    yield item
            else:
                yield res
