from __future__ import annotations

import asyncio
import functools
import time
from collections import defaultdict
from typing import Any, Callable, Coroutine, Dict, Optional, TypeVar

from loguru import logger

F = TypeVar("F", bound=Callable[..., Any])


class PerformanceMetrics:
    """Collect metrics for XenonPie operations."""

    def __init__(self) -> None:
        self._counters: Dict[str, int] = defaultdict(int)
        self._timings: Dict[str, list[float]] = defaultdict(list)
        self._gauges: Dict[str, Any] = {}
        self._lock = asyncio.Lock()

    async def increment(self, name: str, amount: int = 1) -> None:
        async with self._lock:
            self._counters[name] += amount

    async def timing(self, name: str, value: float) -> None:
        async with self._lock:
            self._timings[name].append(value)

    async def gauge(self, name: str, value: Any) -> None:
        async with self._lock:
            self._gauges[name] = value

    async def snapshot(self) -> Dict[str, Any]:
        async with self._lock:
            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "latencies": {
                    name: {
                        "count": len(values),
                        "average_ms": round(sum(values) / len(values) * 1000, 2) if values else 0.0,
                        "max_ms": round(max(values) * 1000, 2) if values else 0.0,
                    }
                    for name, values in self._timings.items()
                },
            }

    def timed(self, metric_name: str) -> Callable[[F], F]:
        def decorator(func: F) -> F:
            if asyncio.iscoroutinefunction(func):
                @functools.wraps(func)
                async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                    start = time.monotonic()
                    try:
                        return await func(*args, **kwargs)
                    finally:
                        elapsed = time.monotonic() - start
                        await metrics.timing(metric_name, elapsed)
                return async_wrapper  # type: ignore[return-value]

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                start = time.monotonic()
                try:
                    return func(*args, **kwargs)
                finally:
                    elapsed = time.monotonic() - start
                    asyncio.create_task(metrics.timing(metric_name, elapsed))
            return sync_wrapper  # type: ignore[return-value]

        return decorator


metrics = PerformanceMetrics()


async def increment_metric(name: str, amount: int = 1) -> None:
    await metrics.increment(name, amount)


async def snapshot_metrics() -> Dict[str, Any]:
    return await metrics.snapshot()
