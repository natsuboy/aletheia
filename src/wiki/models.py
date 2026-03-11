"""Wiki 数据模型"""

from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class WikiPage(BaseModel):
    """Wiki 页面"""

    id: str = Field(..., description="页面 ID")
    title: str = Field(..., description="页面标题")
    content: str = Field(default="", description="Markdown 内容")
    file_paths: List[str] = Field(default_factory=list, description="关联文件路径")
    importance: float = Field(default=0.0, description="重要性评分 (0-1)")
    related_pages: List[str] = Field(default_factory=list, description="关联页面 ID")
    graph_entity_ids: List[str] = Field(default_factory=list, description="关联图谱实体 ID")
    mermaid_diagrams: List[str] = Field(default_factory=list, description="Mermaid 图表")


class WikiSection(BaseModel):
    """Wiki 章节"""

    id: str = Field(..., description="章节 ID")
    title: str = Field(..., description="章节标题")
    pages: List[str] = Field(default_factory=list, description="页面 ID 列表")
    subsections: List[str] = Field(default_factory=list, description="子章节 ID 列表")
    community_id: Optional[int] = Field(default=None, description="社区检测 ID")


class WikiStructure(BaseModel):
    """Wiki 整体结构"""

    id: str = Field(..., description="Wiki ID")
    title: str = Field(..., description="Wiki 标题")
    description: str = Field(default="", description="Wiki 描述")
    pages: Dict[str, WikiPage] = Field(default_factory=dict, description="页面映射")
    sections: Dict[str, WikiSection] = Field(default_factory=dict, description="章节映射")
    root_sections: List[str] = Field(default_factory=list, description="顶层章节 ID")
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="生成时间")
    project_id: str = Field(..., description="项目 ID")
