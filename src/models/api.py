"""API 请求和响应模型"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field, HttpUrl, field_validator
import re


class JobStatus(str, Enum):
    """任务状态"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class IngestionStage(str, Enum):
    """摄取阶段"""

    CLONING = "cloning"
    INDEXING = "indexing"
    UPLOADING = "uploading"  # SCIP 文件上传
    PARSING = "parsing"
    MAPPING = "mapping"
    INSERTING = "inserting"
    VECTORIZING = "vectorizing"
    WIKI_GENERATION = "wiki_generation"
    DELETING = "deleting"  # 项目删除阶段
    COMPLETED = "completed"
    FAILED = "failed"


class IngestRequest(BaseModel):
    """摄取请求"""

    repo_url: HttpUrl = Field(..., description="仓库 URL")
    language: str = Field(
        default="go",
        description="编程语言",
    )
    project_name: Optional[str] = Field(
        None, description="项目名称 (默认从 URL 提取)", min_length=1, max_length=100
    )
    branch: Optional[str] = Field(
        default="main", description="分支名称", min_length=1, max_length=100
    )

    @field_validator('language')
    @classmethod
    def validate_language(cls, v: str) -> str:
        """验证编程语言"""
        supported = {'go', 'python', 'java', 'javascript', 'typescript'}
        v_lower = v.lower()
        if v_lower not in supported:
            raise ValueError(f"不支持的编程语言: {v}. 支持的语言: {', '.join(supported)}")
        return v_lower

    @field_validator('project_name')
    @classmethod
    def sanitize_project_name(cls, v: Optional[str]) -> Optional[str]:
        """清理项目名称"""
        if v is None:
            return None
        # 移除危险字符
        sanitized = re.sub(r'[^\w\-]', '_', v)
        if sanitized != v:
            raise ValueError(f"项目名称包含非法字符，只能包含字母、数字、连字符和下划线")
        return sanitized

    @field_validator('branch')
    @classmethod
    def validate_branch(cls, v: str) -> str:
        """验证分支名称"""
        if not re.match(r'^[\w\-./]+$', v):
            raise ValueError(f"无效的分支名称: {v}")
        return v


class IngestResponse(BaseModel):
    """摄取响应"""

    job_id: str = Field(..., description="任务 ID")
    project_name: str = Field(..., description="项目名称")
    status: JobStatus = Field(..., description="任务状态")
    message: str = Field(..., description="提示信息")


class JobStatusResponse(BaseModel):
    """任务状态响应"""

    job_id: str = Field(..., description="任务 ID")
    project_name: str = Field(..., description="项目名称")
    status: JobStatus = Field(..., description="任务状态")
    stage: Optional[IngestionStage] = Field(None, description="当前阶段")
    progress: float = Field(default=0.0, description="进度百分比 (0-100)")
    message: Optional[str] = Field(None, description="状态消息")
    error: Optional[str] = Field(None, description="错误信息")
    trace_id: Optional[str] = Field(None, description="链路追踪 ID")
    retry_count: int = Field(default=0, description="重试次数")
    failure_class: Optional[str] = Field(None, description="失败分类")
    write_phase: Optional[str] = Field(default=None, description="写入阶段")
    items_total: Optional[int] = Field(default=None, description="当前阶段总量")
    items_done: Optional[int] = Field(default=None, description="当前阶段已完成量")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")


class GraphDataRequest(BaseModel):
    """图谱数据请求"""

    project_id: str = Field(..., description="项目 ID")
    limit: Optional[int] = Field(default=100, description="返回节点数量限制")
    node_types: Optional[List[str]] = Field(None, description="节点类型过滤")

    @field_validator('project_id')
    @classmethod
    def validate_project_id(cls, v: str) -> str:
        """验证项目 ID"""
        if v.startswith("project:"):
            v = v[len("project:"):]
        if not re.match(r'^[a-zA-Z0-9_-]{1,100}$', v):
            raise ValueError(f"无效的项目 ID 格式: {v}")
        # 防止路径遍历
        if '..' in v or v.startswith('/'):
            raise ValueError(f"项目 ID 包含非法字符: {v}")
        return v

    @field_validator('limit')
    @classmethod
    def validate_limit(cls, v: int) -> int:
        """验证限制值"""
        if v <= 0 or v > 10000:
            raise ValueError("limit 必须在 1-10000 之间")
        return v


class GraphNodeResponse(BaseModel):
    """图节点响应"""

    id: str
    label: str
    properties: Dict[str, Any]


class GraphEdgeResponse(BaseModel):
    """图边响应"""

    id: str
    from_id: str
    to_id: str
    type: str
    properties: Dict[str, Any]


class GraphDataResponse(BaseModel):
    """图谱数据响应"""

    nodes: List[GraphNodeResponse]
    edges: List[GraphEdgeResponse]
    stats: Dict[str, int] = Field(default_factory=dict, description="统计信息")


class GinEndpointHit(BaseModel):
    """Gin 接口定位命中项"""

    method: str = Field(..., description="HTTP 方法")
    route: str = Field(..., description="路由路径")
    handler_symbol: str = Field(..., description="处理函数符号")
    file_path: str = Field(..., description="处理函数文件路径")
    start_line: Optional[int] = Field(None, description="处理函数起始行（1-based）")
    node_id: Optional[str] = Field(None, description="关联图节点 ID")
    score: float = Field(default=0.0, description="匹配得分")


class GinEndpointSearchResponse(BaseModel):
    """Gin 接口搜索响应"""

    project: str = Field(..., description="项目名称")
    query: str = Field(default="", description="搜索关键词")
    total: int = Field(default=0, description="命中总数")
    hits: List[GinEndpointHit] = Field(default_factory=list, description="命中列表")


class NavReferenceNode(BaseModel):
    """引用子图节点"""

    id: str
    name: str
    label: str
    file_path: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None


class NavReferenceEdge(BaseModel):
    """引用子图边"""

    source_id: str
    target_id: str
    rel_type: str
    direction: Literal["outgoing", "incoming"]


class ReferenceSubgraphResponse(BaseModel):
    """引用关系子图响应"""

    project: str
    symbol: str
    center_node_id: str
    depth: int
    direction: Literal["in", "out", "both"]
    truncated: bool = False
    stats: Dict[str, int] = Field(default_factory=dict)
    nodes: List[NavReferenceNode] = Field(default_factory=list)
    edges: List[NavReferenceEdge] = Field(default_factory=list)


class EntrypointReverseLookupResponse(BaseModel):
    """节点到入口接口反查响应"""

    project: str
    node_id: str
    hits: List[GinEndpointHit] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    """错误响应"""

    error: str = Field(..., description="错误类型")
    message: str = Field(..., description="错误消息")
    detail: Optional[Dict[str, Any]] = Field(None, description="详细信息")


class ChatMessage(BaseModel):
    """聊天消息"""
    role: str = Field(..., description="角色: user/assistant")
    content: str = Field(..., description="消息内容")


class ChatRequest(BaseModel):
    """聊天请求"""

    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="用户查询",
    )
    project_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="项目 ID",
    )
    stream: bool = Field(default=True, description="是否流式响应")
    session_id: Optional[str] = Field(
        None,
        max_length=100,
        pattern=r'^[a-zA-Z0-9_\-]{1,100}$',
        description="会话 ID（多轮对话）",
    )

    @field_validator('query')
    @classmethod
    def validate_query(cls, v: str) -> str:
        """验证查询内容"""
        query = v.strip()

        # 检查空查询
        if not query:
            raise ValueError("查询不能为空")

        # 检查潜在的注入攻击
        dangerous_patterns = [
            r'<script[^>]*>.*?</script>',  # XSS
            r'javascript:',  # XSS
            r'on\w+\s*=',  # 事件处理器注入
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                raise ValueError("查询包含危险模式")

        # 检查可疑的 SQL/Cypher 关键字（额外安全层）
        suspicious_keywords = [
            'DROP', 'DELETE', 'TRUNCATE', 'ALTER', 'EXEC',
            'EXECUTE', 'INSERT INTO', 'UPDATE SET'
        ]
        query_upper = query.upper()
        for keyword in suspicious_keywords:
            if keyword in query_upper:
                raise ValueError(f"查询包含潜在危险的关键字: {keyword}")

        return query

    @field_validator('project_id')
    @classmethod
    def validate_project_id(cls, v: str) -> str:
        """验证项目 ID"""
        if v.startswith("project:"):
            v = v[len("project:"):]
        if not re.match(r'^[a-zA-Z0-9_-]{1,100}$', v):
            raise ValueError(f"无效的项目 ID 格式: {v}")
        # 防止路径遍历
        if '..' in v or v.startswith('/'):
            raise ValueError(f"项目 ID 包含非法字符: {v}")
        return v


class ChatResponse(BaseModel):
    """聊天响应"""

    answer: str = Field(..., description="回答")
    sources: List[Dict[str, Any]] = Field(default_factory=list, description="来源")
    evidence: List[Dict[str, Any]] = Field(default_factory=list, description="证据条目")
    intent: str = Field(..., description="查询意图")
    quality_score: float = Field(default=0.0, description="回答质量分 (0-1)")
    retrieval_trace_id: str = Field(default="", description="检索链路追踪ID")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")


class FileContentResponse(BaseModel):
    """文件内容响应"""

    path: str = Field(..., description="文件相对路径")
    content: str = Field(..., description="文件内容")
    language: str = Field(default="text", description="编程语言")


class ScipIngestWithSourceRequest(BaseModel):
    """SCIP文件摄取请求（带源码）

    支持三种源码提供方式：
    1. local_path - 本地源码路径
    2. zip_file - 源码压缩文件
    3. gitlab_repo - GitLab仓库地址
    """

    project_name: str = Field(..., min_length=1, max_length=100, description="项目名称")

    # SCIP文件路径（必填）
    scip_path: str = Field(..., description="SCIP索引文件路径（本地路径或容器内路径）")

    # 源码类型（三选一）
    source_type: str = Field(
        ...,
        description="源码类型: local_path|zip_file|gitlab_repo",
    )

    # 方式1：本地路径
    local_source_path: Optional[str] = Field(
        None, description="源码本地路径（source_type=local_path时必填）"
    )

    # 方式2：压缩文件
    source_zip_path: Optional[str] = Field(
        None, description="源码压缩文件路径（source_type=zip_file时必填）"
    )

    # 方式3：GitLab仓库
    gitlab_repo: Optional[str] = Field(
        None, description="GitLab仓库地址（source_type=gitlab_repo时必填）"
    )
    gitlab_branch: Optional[str] = Field("main", description="GitLab分支名（默认main）")
    gitlab_token: Optional[str] = Field(None, description="GitLab访问Token（可选，用于私有仓库）")

    @field_validator('project_name')
    @classmethod
    def sanitize_project_name(cls, v: str) -> str:
        """清理项目名称"""
        sanitized = re.sub(r'[^\w\-]', '_', v)
        if sanitized != v:
            raise ValueError(f"项目名称包含非法字符，只能包含字母、数字、连字符和下划线")
        return sanitized

    @field_validator('source_type')
    @classmethod
    def validate_source_type(cls, v: str) -> str:
        """验证源码类型"""
        valid_types = {'local_path', 'zip_file', 'gitlab_repo'}
        if v not in valid_types:
            raise ValueError(f"无效的源码类型: {v}. 必须是: {', '.join(valid_types)}")
        return v

    @field_validator('scip_path', 'local_source_path', 'source_zip_path')
    @classmethod
    def sanitize_path(cls, v: Optional[str]) -> Optional[str]:
        """清理文件路径"""
        if v is None:
            return None
        # 防止路径遍历
        if '..' in v or v.startswith('/'):
            # 允许绝对路径，但警告
            pass
        return v

    @field_validator('gitlab_repo')
    @classmethod
    def validate_gitlab_url(cls, v: Optional[str]) -> Optional[str]:
        """验证 GitLab URL"""
        if v is None:
            return None
        # 基本验证
        if not re.match(r'^https?://', v):
            raise ValueError(f"无效的 GitLab URL: {v}")
        return v


class ScipIngestOnlyRequest(BaseModel):
    """SCIP文件直接摄取请求

    快速通道：跳过Git clone和SCIP生成，直接使用已有SCIP文件
    """

    scip_path: str = Field(..., description="SCIP索引文件路径")
    project_name: str = Field(..., min_length=1, max_length=100, description="项目名称")

    # 可选：源码提供者配置
    source_type: Optional[str] = Field(
        None,
        description="源码类型（可选）: local_path|zip_file|gitlab_repo",
    )
    source_config: Optional[Dict[str, Any]] = Field(
        None, description="源码配置（根据source_type提供对应参数）"
    )

    @field_validator('project_name')
    @classmethod
    def sanitize_project_name(cls, v: str) -> str:
        """清理项目名称"""
        sanitized = re.sub(r'[^\w\-]', '_', v)
        if sanitized != v:
            raise ValueError(f"项目名称包含非法字符")
        return sanitized

    @field_validator('source_type')
    @classmethod
    def validate_source_type(cls, v: Optional[str]) -> Optional[str]:
        """验证源码类型"""
        if v is None:
            return None
        valid_types = {'local_path', 'zip_file', 'gitlab_repo'}
        if v not in valid_types:
            raise ValueError(f"无效的源码类型: {v}")
        return v
