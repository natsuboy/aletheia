"""健康检查端点"""
from fastapi import APIRouter, status
from pydantic import BaseModel


router = APIRouter(prefix="/api", tags=["health"])


class HealthResponse(BaseModel):
    """健康检查响应"""

    status: str
    version: str


@router.get("/health", response_model=HealthResponse, status_code=status.HTTP_200_OK)
async def health_check():
    """健康检查端点"""
    return HealthResponse(status="ok", version="0.1.0")
