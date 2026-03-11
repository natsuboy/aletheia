"""全局错误处理中间件"""
from fastapi import Request, status
from fastapi.responses import JSONResponse
from loguru import logger


async def error_handler_middleware(request: Request, call_next):
    """全局错误处理"""
    try:
        response = await call_next(request)
        return response
    except ValueError as e:
        logger.error(f"ValueError: {e}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "bad_request", "message": str(e)},
        )
    except KeyError as e:
        logger.error(f"KeyError: {e}")
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "not_found", "message": f"Resource not found: {e}"},
        )
    except Exception as e:
        logger.exception(f"Unhandled exception: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "internal_server_error", "message": "An unexpected error occurred"},
        )
