"""DeepResearch 数据模型"""

from datetime import datetime
from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field


class ResearchIteration(BaseModel):
    """单次研究迭代"""

    iteration: int = Field(..., description="迭代序号")
    query: str = Field(..., description="本轮探索查询")
    findings: str = Field(..., description="本轮发现")
    graph_entities_explored: List[str] = Field(
        default_factory=list, description="本轮探索的图谱实体 ID"
    )
    sources: List[Dict[str, Any]] = Field(
        default_factory=list, description="引用来源"
    )


class ResearchSession(BaseModel):
    """研究会话"""

    id: str = Field(..., description="会话 ID")
    project_id: str = Field(..., description="项目 ID")
    original_query: str = Field(..., description="原始研究问题")
    iterations: List[ResearchIteration] = Field(
        default_factory=list, description="迭代列表"
    )
    status: Literal["active", "concluded"] = Field(
        default="active", description="会话状态"
    )
    max_iterations: int = Field(default=5, description="最大迭代次数")
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="创建时间"
    )
