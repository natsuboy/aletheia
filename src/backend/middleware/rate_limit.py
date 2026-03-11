"""速率限制中间件"""
import time
import threading
from collections import defaultdict
from functools import wraps
from fastapi import Request, HTTPException
try:
    from loguru import logger
except ModuleNotFoundError:  # pragma: no cover - fallback for minimal test env
    import logging
    logger = logging.getLogger(__name__)

from src.backend.config import get_settings


class RateLimiter:
    """简单的内存速率限制器

    生产环境应使用 Redis 或类似的后端
    """

    def __init__(self, requests_per_minute: int = 60):
        """
        初始化速率限制器

        Args:
            requests_per_minute: 每分钟允许的请求数
        """
        self.requests_per_minute = requests_per_minute
        # 存储 {identifier: [(timestamp, ...)]}
        self.requests = defaultdict(list)
        # 清理过期数据的间隔（秒）
        self.cleanup_interval = 300
        self.last_cleanup = 0

    def _cleanup(self) -> None:
        """清理过期的请求记录"""
        now = time.time()
        cutoff = now - 60  # 保留最近 60 秒的记录
        for identifier in list(self.requests.keys()):
            self.requests[identifier] = [
                ts for ts in self.requests[identifier]
                if ts > cutoff
            ]
            if not self.requests[identifier]:
                del self.requests[identifier]
        self.last_cleanup = now

    def is_allowed(self, identifier: str) -> bool:
        """
        检查是否允许请求

        Args:
            identifier: 唯一标识符（如 IP 地址）

        Returns:
            是否允许请求
        """
        if time.time() - self.last_cleanup > self.cleanup_interval:
            self._cleanup()

        now = time.time()
        cutoff = now - 60  # 60 秒窗口

        # 获取窗口内的请求数
        recent_requests = [
            ts for ts in self.requests[identifier]
            if ts > cutoff
        ]

        if len(recent_requests) >= self.requests_per_minute:
            logger.warning(
                f"Rate limit exceeded for {identifier}: "
                f"{len(recent_requests)} requests in last 60s"
            )
            return False

        # 记录本次请求
        self.requests[identifier].append(now)
        return True

    def get_retry_after(self, identifier: str) -> int:
        """
        获取重试等待时间（秒）

        Args:
            identifier: 唯一标识符

        Returns:
            需要等待的秒数
        """
        if not self.requests[identifier]:
            return 0

        # 获取最早的未过期请求
        oldest_recent = min(ts for ts in self.requests[identifier] if ts > time.time() - 60)
        retry_after = int(oldest_recent + 60 - time.time())
        return max(0, retry_after)


# 全局速率限制器实例
_rate_limiters: dict[str, RateLimiter] = {}
_rate_limiters_lock = threading.Lock()


def get_rate_limiter(key: str = "default") -> RateLimiter:
    """
    获取或创建速率限制器实例

    Args:
        key: 限制器标识符

    Returns:
        RateLimiter 实例
    """
    with _rate_limiters_lock:
        if key not in _rate_limiters:
            settings = get_settings()
            _rate_limiters[key] = RateLimiter(
                requests_per_minute=settings.rate_limit_per_minute
            )
        return _rate_limiters[key]


def rate_limit(requests_per_minute: int = None):
    """
    速率限制装饰器

    Args:
        requests_per_minute: 每分钟请求数（默认从配置读取）

    Usage:
        @router.get("/api/endpoint")
        @rate_limit(10)  # 每分钟 10 次请求
        async def endpoint():
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 从参数中提取 Request 对象
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break

            if not request:
                # 如果不在参数中，尝试从 kwargs 获取
                request = kwargs.get('request')

            if request:
                # 使用客户端 IP 作为标识符
                identifier = request.client.host if request.client else "unknown"

                limiter = get_rate_limiter(func.__name__)
                if requests_per_minute:
                    limiter.requests_per_minute = requests_per_minute

                if not limiter.is_allowed(identifier):
                    retry_after = limiter.get_retry_after(identifier)
                    raise HTTPException(
                        status_code=429,
                        detail={
                            "error": "rate_limit_exceeded",
                            "message": f"Rate limit exceeded. Try again in {retry_after} seconds.",
                            "retry_after": retry_after
                        },
                        headers={"Retry-After": str(retry_after)}
                    )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


class RateLimitMiddleware:
    """全局速率限制中间件"""

    def __init__(self, app, requests_per_minute: int = 60):
        """
        初始化中间件

        Args:
            app: FastAPI 应用
            requests_per_minute: 每分钟请求数
        """
        self.app = app
        self.limiter = RateLimiter(requests_per_minute)

    async def __call__(self, scope, receive, send):
        """
        处理请求

        Args:
            scope: ASGI scope
            receive: ASGI receive
            send: ASGI send
        """
        if scope['type'] == 'http':
            # 从客户端 IP 获取标识符
            client_host = scope.get('client', ('unknown',))[0]
            identifier = client_host

            if not self.limiter.is_allowed(identifier):
                retry_after = self.limiter.get_retry_after(identifier)

                # 发送 429 响应
                from fastapi.responses import JSONResponse

                response = JSONResponse(
                    status_code=429,
                    content={
                        "error": "rate_limit_exceeded",
                        "message": f"Rate limit exceeded. Try again in {retry_after} seconds.",
                        "retry_after": retry_after
                    },
                    headers={"Retry-After": str(retry_after)}
                )

                await response(scope, receive, send)
                return

        # 继续处理请求
        await self.app(scope, receive, send)
