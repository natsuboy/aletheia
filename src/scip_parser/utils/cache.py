"""
缓存管理和性能监控
"""

from __future__ import annotations

import functools
import time
from dataclasses import dataclass
from typing import Any, Callable, ContextManager, TypeVar

T = TypeVar("T")


class CacheManager:
    """简单缓存管理器"""

    _instance = None

    def __init__(self):
        self._cache: dict[str, Any] = {}

    @classmethod
    def get_instance(cls) -> CacheManager:
        if cls._instance is None:
            cls._instance = CacheManager()
        return cls._instance

    def get(self, key: str) -> Any | None:
        return self._cache.get(key)

    def set(self, key: str, value: Any) -> None:
        self._cache[key] = value

    def clear(self) -> None:
        self._cache.clear()


def cached(func: Callable[..., T]) -> Callable[..., T]:
    """简单的缓存装饰器"""
    cache: dict[str, T] = {}

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        # Create key from args/kwargs
        # Note: args must be hashable
        key = str(args) + str(kwargs)
        if key in cache:
            return cache[key]
        result = func(*args, **kwargs)
        cache[key] = result
        return result

    return wrapper


@dataclass
class PerformanceMetrics:
    count: int = 0
    total_time: float = 0.0


class PerformanceMonitor:
    """性能监控器"""

    def __init__(self):
        self._metrics: dict[str, PerformanceMetrics] = {}

    def measure(self, name: str) -> ContextManager[None]:
        return _MeasureContext(self, name)

    def record(self, name: str, duration: float) -> None:
        if name not in self._metrics:
            self._metrics[name] = PerformanceMetrics()
        self._metrics[name].count += 1
        self._metrics[name].total_time += duration

    def get_metrics(self) -> dict[str, dict[str, Any]]:
        return {
            name: {"count": m.count, "total_time": m.total_time}
            for name, m in self._metrics.items()
        }


class _MeasureContext:
    def __init__(self, monitor: PerformanceMonitor, name: str):
        self.monitor = monitor
        self.name = name
        self.start_time = 0.0

    def __enter__(self) -> None:
        self.start_time = time.perf_counter()

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        duration = time.perf_counter() - self.start_time
        self.monitor.record(self.name, duration)
