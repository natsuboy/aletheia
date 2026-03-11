"""通用重试装饰器"""
import asyncio
import functools
from dataclasses import dataclass, field
from typing import Tuple, Type

from loguru import logger


@dataclass
class RetryConfig:
    """重试配置"""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    backoff_factor: float = 2.0
    retryable_exceptions: Tuple[Type[Exception], ...] = field(default_factory=lambda: (Exception,))


def with_retry(config: RetryConfig = None):
    """同步重试装饰器"""
    cfg = config or RetryConfig()

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_err = None
            for attempt in range(cfg.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except cfg.retryable_exceptions as e:
                    last_err = e
                    if attempt < cfg.max_retries:
                        delay = min(cfg.base_delay * (cfg.backoff_factor ** attempt), cfg.max_delay)
                        logger.warning(f"Retry {attempt+1}/{cfg.max_retries} for {func.__name__}: {e}, delay={delay:.1f}s")
                        import time
                        time.sleep(delay)
            raise last_err
        return wrapper
    return decorator


def with_async_retry(config: RetryConfig = None):
    """异步重试装饰器"""
    cfg = config or RetryConfig()

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_err = None
            for attempt in range(cfg.max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except cfg.retryable_exceptions as e:
                    last_err = e
                    if attempt < cfg.max_retries:
                        delay = min(cfg.base_delay * (cfg.backoff_factor ** attempt), cfg.max_delay)
                        logger.warning(f"Retry {attempt+1}/{cfg.max_retries} for {func.__name__}: {e}, delay={delay:.1f}s")
                        await asyncio.sleep(delay)
            raise last_err
        return wrapper
    return decorator
