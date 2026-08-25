import inspect
import logging
from typing import Callable, Any, AsyncGenerator, Union
import httpx
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

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
    **kwargs: Any
) -> Any:
    """
    Executes an async function with transient retries using exponential backoff.
    """
    retrier = get_transient_retrier(max_attempts=max_attempts, min_wait=min_wait, max_wait=max_wait)
    async for attempt in retrier:
        with attempt:
            return await async_func(*args, **kwargs)

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
