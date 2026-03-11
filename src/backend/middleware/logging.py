"""请求日志中间件"""
import time
from fastapi import Request
from loguru import logger


async def logging_middleware(request: Request, call_next):
    """记录请求日志"""
    start_time = time.time()

    # 记录请求信息
    logger.info(f"Request: {request.method} {request.url.path}")

    # 处理请求
    response = await call_next(request)

    # 计算处理时间
    process_time = time.time() - start_time
    logger.info(
        f"Response: {response.status_code} | Time: {process_time:.3f}s | Path: {request.url.path}"
    )

    # 添加处理时间到响应头
    response.headers["X-Process-Time"] = str(process_time)

    return response
