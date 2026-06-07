from __future__ import annotations

import asyncio
import functools
import random
import time
from typing import Any, Callable, Iterable, TypeVar

from loguru import logger

F = TypeVar("F", bound=Callable[..., Any])


def retry(
    max_attempts: int = 3,
    initial_delay: float = 0.5,
    max_delay: float = 10.0,
    backoff: float = 2.0,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
    jitter: float = 0.2,
) -> Callable[[F], F]:
    """Retry decorator with exponential backoff for sync and async functions."""

    def decorator(func: F) -> F:
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                delay = initial_delay
                for attempt in range(1, max_attempts + 1):
                    try:
                        return await func(*args, **kwargs)
                    except exceptions as exc:
                        if attempt == max_attempts:
                            logger.error(f"Retry exhausted for {func.__name__}: {exc}")
                            raise
                        sleep_time = min(max_delay, delay) + random.random() * jitter
                        logger.warning(
                            f"Retry {attempt}/{max_attempts} for {func.__name__} after {sleep_time:.2f}s: {exc}"
                        )
                        await asyncio.sleep(sleep_time)
                        delay *= backoff
                return await func(*args, **kwargs)

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            delay = initial_delay
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    if attempt == max_attempts:
                        logger.error(f"Retry exhausted for {func.__name__}: {exc}")
                        raise
                    sleep_time = min(max_delay, delay) + random.random() * jitter
                    logger.warning(
                        f"Retry {attempt}/{max_attempts} for {func.__name__} after {sleep_time:.2f}s: {exc}"
                    )
                    time.sleep(sleep_time)
                    delay *= backoff
            return func(*args, **kwargs)

        return sync_wrapper  # type: ignore[return-value]

    return decorator
