"""Retry utilities with exponential backoff."""
import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

from tenacity import (
    after_log,
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.utils.exceptions import (
    LLMError,
    ProviderUnavailableError,
    RateLimitError,
    SheetsError,
)

T = TypeVar("T")

logger = logging.getLogger(__name__)


def is_transient_error(exc: Exception) -> bool:
    """Determine if an error is transient and worth retrying."""
    if isinstance(exc, (ProviderUnavailableError, RateLimitError)):
        return True
    if isinstance(exc, LLMError) and "timeout" in str(exc).lower():
        return True
    if isinstance(exc, SheetsError) and "rate limit" in str(exc).lower():
        return True
    return isinstance(exc, (asyncio.TimeoutError, ConnectionError, TimeoutError))


def get_retry_decorator(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter: float = 0.1,
):
    """Create a retry decorator with exponential backoff and jitter."""
    return retry(
        reraise=True,
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential_jitter(
            initial=base_delay,
            max=max_delay,
            jitter=jitter,
        ),
        retry=retry_if_exception_type((
            ProviderUnavailableError,
            RateLimitError,
            ConnectionError,
            TimeoutError,
            asyncio.TimeoutError,
        )),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        after=after_log(logger, logging.INFO),
    )


async def async_retry(
    func: Callable[..., Awaitable[T]],
    *args,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter: float = 0.1,
    **kwargs,
) -> T:
    """Execute async function with retry logic."""
    last_exception: BaseException | None = None
    
    for attempt in range(max_attempts):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            if not is_transient_error(e) or attempt == max_attempts - 1:
                raise
            
            delay = min(base_delay * (2 ** attempt) + random.uniform(0, jitter), max_delay)
            logger.warning(
                "Retry attempt: attempt=%d, max_attempts=%d, delay=%.2f, error=%s",
                attempt + 1,
                max_attempts,
                delay,
                str(e),
            )
            await asyncio.sleep(delay)
    
    if last_exception:
        raise last_exception
    raise RuntimeError("Retry loop completed without exception")