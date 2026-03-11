"""摄取 API 端点"""

import asyncio
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends, UploadFile, File, Form
from loguru import logger

from src.models.api import (
    IngestRequest,
    IngestResponse,
    JobStatusResponse,
    JobStatus,
    IngestionStage,
    ScipIngestWithSourceRequest,
    ScipIngestOnlyRequest,
)
from src.backend.config import get_settings, Settings
from src.backend.celery_app import celery_app
from src.graph import GraphClient
from src.backend.security import InputValidator
from src.backend.middleware.rate_limit import rate_limit
from src.backend.job_store import job_store
from src.graph.snapshot_store import GraphSnapshotKeys, sync_get_json, sync_set_json, default_meta, now_iso

router = APIRouter(prefix="/api", tags=["ingest"])


def _mark_snapshot_rebuilding(project_name: str) -> None:
    """任务创建时标记项目快照进入重建态。"""
    try:
        key = GraphSnapshotKeys.meta(project_name)
        meta = sync_get_json(job_store.redis, key) or default_meta()
        meta.update(
            {
                "is_rebuilding": True,
                "last_refresh_status": "running",
                "last_error": None,
                "updated_at": now_iso(),
            }
        )
        sync_set_json(job_store.redis, key, meta)
    except Exception as e:
        logger.warning(f"mark snapshot rebuilding failed ({project_name}): {e}")


def _mark_snapshot_cancelled(project_name: str) -> None:
    """任务取消时复位项目快照重建态，避免读取层持续降级。"""
    try:
        key = GraphSnapshotKeys.meta(project_name)
        meta = sync_get_json(job_store.redis, key) or default_meta()
        meta.update(
            {
                "is_rebuilding": False,
                "last_refresh_status": "cancelled",
                "last_error": "任务已取消",
                "updated_at": now_iso(),
            }
        )
        sync_set_json(job_store.redis, key, meta)
    except Exception as e:
        logger.warning(f"mark snapshot cancelled failed ({project_name}): {e}")


def get_graph_client():
    """依赖注入: 获取图数据库客户端"""
    client = GraphClient()
    try:
        client.connect()
    except Exception as e:
        logger.error(f"Memgraph 连接失败: {e}")
        raise HTTPException(status_code=503, detail=f"图数据库不可用: {e}")
    try:
        yield client
    finally:
        client.close()


@router.post(
    "/ingest",
    response_model=IngestResponse,
    summary="提交代码仓库摄取任务",
    description="""
异步摄取代码仓库，构建代码知识图谱。

## 工作流程

1. **验证**: 验证仓库 URL、语言、项目名称
2. **克隆**: Git clone 目标仓库
3. **索引**: 运行 SCIP 索引器生成 .scip 文件
4. **解析**: 解析 SCIP 文件提取结构信息
5. **映射**: 转换为图节点和边
6. **批量插入**: 节点使用 UNWIND，边使用 LOAD CSV 批量导入 Memgraph

## 支持的语言

- **go**: 使用 scip-go 索引器
- **python**: 计划中
- **java**: 计划中
- **javascript/typescript**: 计划中

## 限制

- 仓库 URL: 必须是有效的 HTTP/HTTPS/SSH URL
- 项目名称: 1-100 字符
- 分支名称: 1-100 字符
- 速率限制: 10 请求/分钟（更严格）

## 任务状态

使用 GET `/api/jobs/{job_id}` 查询任务进度。

## 示例

```json
{
  "repo_url": "https://github.com/sourcegraph/sourcegraph.git",
  "language": "go",
  "project_name": "sourcegraph",
  "branch": "main"
}
```
""",
    responses={
        200: {"description": "任务成功创建"},
        400: {"description": "输入验证失败"},
        429: {"description": "超过速率限制"},
        500: {"description": "服务器内部错误"},
    },
)
@rate_limit(requests_per_minute=10)  # 摄取端点: 10 请求/分钟（更严格的限制）
async def ingest_repository(
    data: IngestRequest,
    background_tasks: BackgroundTasks,
    settings: Settings = Depends(get_settings),
):
    """
    提交代码仓库摄取任务

    - **repo_url**: 仓库 URL (HTTP/HTTPS/SSH)
    - **language**: 编程语言 (当前支持: go, python, java, javascript, typescript)
    - **project_name**: 项目名称 (可选, 默认从 URL 提取)
    - **branch**: 分支名称 (默认: main)

    返回任务 ID, 可使用 GET /api/jobs/{job_id} 查询进度
    """
    # 验证输入
    try:
        validated_repo_url = InputValidator.validate_repo_url(str(data.repo_url))
        validated_language = InputValidator.validate_language(data.language)
        validated_project_name = InputValidator.sanitize_log_message(data.project_name or "")
        validated_branch = InputValidator.validate_branch_name(data.branch or "main")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}")

    # 生成任务 ID (注意：Celery 也会生成 ID，但为了控制，我们先生成并传递给 Celery)
    job_id = str(uuid.uuid4())

    # 提取项目名称
    if not data.project_name:
        # 从 URL 提取 (例如: https://github.com/user/repo.git -> repo)
        project_name = validated_repo_url.rstrip("/").split("/")[-1].replace(".git", "")
    else:
        project_name = validated_project_name

    logger.info(
        f"收到摄取请求: job_id={job_id}, "
        f"project={project_name}, "
        f"repo={validated_repo_url}, "
        f"lang={validated_language}"
    )

    # 初始化任务状态到 Redis
    job_data = {
        "job_id": job_id,
        "project_name": project_name,
        "repo_url": validated_repo_url,
        "language": validated_language,
        "branch": validated_branch,
        "status": JobStatus.PENDING.value,
        "stage": None,
        "progress": 0,
        "message": "任务已创建,等待执行",
        "error": None,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "completed_at": None,
        "write_phase": "prepare",
        "items_total": None,
        "items_done": None,
    }
    job_store.set(job_id, job_data)
    job_store.set_project_active_job(project_name, job_id)
    _mark_snapshot_rebuilding(project_name)

    # 提交 Celery 任务
    celery_app.send_task(
        "src.ingestion.tasks.ingest_repository",
        args=[validated_repo_url, validated_language, project_name, validated_branch],
        task_id=job_id,
    )

    return IngestResponse(
        job_id=job_id,
        project_name=project_name,
        status=JobStatus.PENDING,
        message="摄取任务已提交,正在队列中等待执行",
    )


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """
    查询任务状态

    - **job_id**: 任务 ID (由 POST /api/ingest 返回)
    """
    job_data = job_store.get(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail=f"任务 {job_id} 不存在")

    return JobStatusResponse(**job_data)


@router.get("/projects/{project_name}/jobs/active")
async def get_project_active_job(project_name: str):
    """按项目查询当前活跃 ingestion 任务（用于页面刷新后恢复进度）。"""
    job_id = job_store.get_project_active_job(project_name)
    if not job_id:
        return {"active": False, "job": None}

    job_data = job_store.get(job_id)
    if not job_data:
        return {"active": False, "job": None}

    status = str(job_data.get("status") or "")
    active = status in {JobStatus.PENDING.value, JobStatus.RUNNING.value}
    return {"active": active, "job": job_data}


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    """取消摄取任务（幂等）。"""
    job_data = job_store.get(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail=f"任务 {job_id} 不存在")

    status = job_data.get("status")
    if status not in {JobStatus.PENDING.value, JobStatus.RUNNING.value}:
        project_name = job_data.get("project_name", "")
        stage = str(job_data.get("stage") or "")
        if stage == "cancelled" and project_name:
            job_store.clear_project_active_job(project_name)
            _mark_snapshot_cancelled(project_name)
        return {
            "job_id": job_id,
            "status": "already_finished",
            "current_status": status,
            "message": "任务已处于终态，无需取消",
        }

    celery_app.control.revoke(job_id, terminate=True)

    project_name = job_data.get("project_name", "")
    try:
        job_store.update(job_id, {
            "status": JobStatus.FAILED.value,
            "stage": "cancelled",
            "error": "任务已被用户取消",
            "message": "任务已取消",
        })
        job_store.clear_project_active_job(project_name)
        _mark_snapshot_cancelled(project_name)
    except Exception as e:
        logger.error(f"Failed to cancel job {job_id}: {e}")
        try:
            job_store.clear_project_active_job(project_name)
        except:
            pass
        raise HTTPException(status_code=500, detail=f"取消任务失败: {str(e)}")

    return {"job_id": job_id, "status": "cancelled"}


@router.get("/projects")
async def list_projects(graph_client: GraphClient = Depends(get_graph_client)):
    """
    列出所有已摄取的项目
    """
    query = """
    MATCH (p:Project)
    RETURN p.id as id, p.name as name, p.project_root as root
    ORDER BY p.name
    """

    results = graph_client.execute_query(query)
    return {
        "projects": [
            {
                "id": r["id"],
                "name": r["name"],
                "root": r.get("root", ""),
            }
            for r in results
        ],
        "total": len(results),
    }


@router.get("/projects/{project_name}")
async def get_project(project_name: str, graph_client: GraphClient = Depends(get_graph_client)):
    """获取单个项目详情"""
    project_id = project_name if project_name.startswith("project:") else f"project:{project_name}"
    query = """
    MATCH (p:Project {id: $pid})
    OPTIONAL MATCH (p)-[:CONTAINS]->(f:File)
    WITH p, count(f) as file_count
    OPTIONAL MATCH (p)-[:CONTAINS*]->(n)
    WHERE NOT n:Project AND NOT n:File
    RETURN p.id as id, p.name as name, p.project_root as root,
           file_count, count(n) as symbol_count
    """
    results = graph_client.execute_query(query, {"pid": project_id})
    if not results:
        raise HTTPException(status_code=404, detail=f"项目 {project_name} 不存在")
    r = results[0]
    return {
        "id": r["id"], "name": r["name"], "root": r.get("root", ""),
        "file_count": r.get("file_count", 0), "symbol_count": r.get("symbol_count", 0),
    }


@router.delete("/projects/{project_name}")
async def delete_project(project_name: str, graph_client: GraphClient = Depends(get_graph_client)):
    """异步删除项目及其所有图数据，返回 job_id 供前端轮询"""
    project_id = project_name if project_name.startswith("project:") else f"project:{project_name}"
    # 检查项目是否存在
    check = graph_client.execute_query(
        "MATCH (p:Project {id: $pid}) RETURN p", {"pid": project_id}
    )
    if not check:
        raise HTTPException(status_code=404, detail=f"项目 {project_name} 不存在")

    pure_name = project_name.removeprefix("project:")
    job_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    job_store.set(job_id, {
        "job_id": job_id,
        "project_name": pure_name,
        "status": "pending",
        "stage": "deleting",
        "progress": 0,
        "message": "删除任务已提交",
        "created_at": now,
        "updated_at": now,
    })

    from src.ingestion.tasks import delete_project_task
    delete_project_task.apply_async(args=[pure_name], task_id=job_id)

    return {"job_id": job_id, "message": "删除任务已提交"}


@router.post("/ingest/scip-upload")
async def upload_scip_file(
    file: UploadFile = File(...),
    project_name: str = Form(...),
):
    """
    直接上传 SCIP 文件进行摄取（跳过 Git 克隆和索引生成）

    - **file**: SCIP 索引文件 (.scip)
    - **project_name**: 项目名称
    """
    job_id = str(uuid.uuid4())

    try:
        validated_project_name = InputValidator.sanitize_log_message(project_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid project name: {str(e)}")

    logger.info(
        f"收到 SCIP 上传请求: job_id={job_id}, "
        f"project={validated_project_name}, "
        f"filename={file.filename}"
    )

    # 保存文件到 api/worker 共享卷
    temp_dir = Path(f"/data/uploads/{validated_project_name}")
    temp_dir.mkdir(parents=True, exist_ok=True)
    scip_file_path = temp_dir / f"{job_id}.scip"
    try:
        content = await file.read()
        scip_file_path.write_bytes(content)
    except OSError as e:
        raise HTTPException(status_code=507, detail=f"磁盘空间不足: {str(e)}")

    job_store.set(job_id, {
        "job_id": job_id,
        "project_name": validated_project_name,
        "status": JobStatus.PENDING.value,
        "stage": IngestionStage.UPLOADING.value,
        "progress": 0,
        "message": "任务已提交，等待处理...",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "write_phase": "prepare",
        "items_total": None,
        "items_done": None,
    })
    job_store.set_project_active_job(validated_project_name, job_id)
    _mark_snapshot_rebuilding(validated_project_name)

    # 派发给 Celery worker（不阻塞 API 进程）
    from src.ingestion.tasks import ingest_scip_file_task
    ingest_scip_file_task.apply_async(
        args=[str(scip_file_path), validated_project_name, None, None],
        task_id=job_id,
        queue="ingestion",
    )

    return IngestResponse(
        job_id=job_id,
        project_name=validated_project_name,
        status=JobStatus.PENDING,
        message="SCIP 文件上传任务已提交",
    )


@router.post(
    "/ingest/scip-with-source",
    response_model=IngestResponse,
    summary="上传SCIP文件并获取源码进行摄取",
    description="""
    上传SCIP文件并支持三种方式获取源码：
    
    1. **本地路径**: 直接使用本地源码目录
    2. **压缩文件**: 上传源码ZIP文件并自动解压
    3. **GitLab仓库**: 从GitLab克隆源码（支持Token认证）
    
    ## 参数说明
    
    - **project_name**: 项目名称（必填）
    - **scip_path**: SCIP文件路径（必填）
    - **source_type**: 源码类型（必填）: local_path|zip_file|gitlab_repo
    - **local_source_path**: 源码本地路径（source_type=local_path时必填）
    - **source_zip_path**: 源码ZIP路径（source_type=zip_file时必填）
    - **gitlab_repo**: GitLab仓库地址（source_type=gitlab_repo时必填）
    - **gitlab_branch**: GitLab分支（可选，默认main）
    - **gitlab_token**: GitLab访问Token（可选）
    
    ## 使用示例
    
    # 方式1：本地源码
    {
      "project_name": "goods-manager-svc",
      "scip_path": "/path/to/index.scip",
      "source_type": "local_path",
      "local_source_path": "/path/to/source"
    }
    
    # 方式2：ZIP文件
    {
      "project_name": "goods-manager-svc",
      "scip_path": "/path/to/index.scip",
      "source_type": "zip_file",
      "source_zip_path": "/path/to/source.zip"
    }
    
    # 方式3：GitLab仓库
    {
      "project_name": "goods-manager-svc",
      "scip_path": "/path/to/index.scip",
      "source_type": "gitlab_repo",
      "gitlab_repo": "https://gitlab.com/user/repo.git",
      "gitlab_branch": "main",
      "gitlab_token": "your_token_here"
    }
    """,
)
async def ingest_scip_with_source(
    background_tasks: BackgroundTasks,
    scip_file: UploadFile = File(...),
    project_name: str = Form(...),
    source_type: str = Form(...),
    local_source_path: Optional[str] = Form(None),
    source_zip_path: Optional[str] = Form(None),
    gitlab_repo: Optional[str] = Form(None),
    gitlab_branch: Optional[str] = Form("main"),
    gitlab_token: Optional[str] = Form(None),
):
    """
    上传SCIP文件并获取源码进行摄取

    支持：
    1. 本地源码路径（source_type=local_path）
    2. 源码压缩文件（source_type=zip_file）
    3. GitLab仓库（source_type=gitlab_repo）
    """
    # 验证项目名称
    try:
        validated_project_name = InputValidator.sanitize_log_message(project_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid project name: {str(e)}")

    # 验证source_type与参数匹配
    if source_type == "local_path" and not local_source_path:
        raise HTTPException(
            status_code=400, detail="local_source_path is required when source_type=local_path"
        )
    if source_type == "zip_file" and not source_zip_path:
        raise HTTPException(
            status_code=400, detail="source_zip_path is required when source_type=zip_file"
        )
    if source_type == "gitlab_repo" and not gitlab_repo:
        raise HTTPException(
            status_code=400, detail="gitlab_repo is required when source_type=gitlab_repo"
        )

    # 生成任务ID
    job_id = str(uuid.uuid4())

    logger.info(
        f"收到SCIP+源码摄取请求: job_id={job_id}, "
        f"project={validated_project_name}, source_type={source_type}"
    )

    # 初始化任务状态
    job_data = {
        "job_id": job_id,
        "project_name": validated_project_name,
        "status": JobStatus.PENDING.value,
        "stage": IngestionStage.UPLOADING.value,
        "progress": 0,
        "message": "任务已创建,等待执行",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "write_phase": "prepare",
        "items_total": None,
        "items_done": None,
    }
    job_store.set(job_id, job_data)
    job_store.set_project_active_job(validated_project_name, job_id)
    _mark_snapshot_rebuilding(validated_project_name)

    # 构建source_config参数
    source_config = {
        "local_source_path": local_source_path,
        "source_zip_path": source_zip_path,
        "gitlab_repo": gitlab_repo,
        "gitlab_branch": gitlab_branch,
        "gitlab_token": gitlab_token,
    }

    # 保存SCIP文件（如果上传了）
    scip_file_path: Optional[Path] = None
    if scip_file:
        temp_dir = Path(f"/tmp/aletheia/{validated_project_name}")
        temp_dir.mkdir(parents=True, exist_ok=True)
        scip_file_path = temp_dir / "index.scip"
        try:
            content = await scip_file.read()
            scip_file_path.write_bytes(content)
            logger.info(f"SCIP file saved: {scip_file_path} ({len(content)} bytes)")
        except OSError as e:
            raise HTTPException(status_code=507, detail=f"磁盘空间不足: {str(e)}")

    # 验证SCIP文件路径
    if not scip_file_path:
        raise HTTPException(status_code=400, detail="SCIP file is required")

    # 提交Celery任务
    celery_app.send_task(
        "src.ingestion.tasks.ingest_scip_file",
        args=[
            str(scip_file_path),
            validated_project_name,
            source_type,
            source_config,
        ],
        task_id=job_id,
    )

    return IngestResponse(
        job_id=job_id,
        project_name=validated_project_name,
        status=JobStatus.PENDING,
        message="SCIP+源码摄取任务已提交",
    )


@router.post(
    "/ingest/scip-only",
    response_model=IngestResponse,
    summary="直接摄取SCIP文件（快速通道）",
    description="""
    快速通道：跳过Git clone和SCIP生成，直接使用已有SCIP文件进行摄取。
    
    ## 参数说明
    
    - **scip_path**: SCIP文件路径（必填）
    - **project_name**: 项目名称（必填）
    - **source_type**: 可选的源码类型（用于代码提取）: local_path|zip_file|gitlab_repo
    - **source_config**: 源码配置字典（根据source_type提供）
    
    ## 使用示例
    
    # 基础：仅SCIP文件
    {
      "scip_path": "/path/to/index.scip",
      "project_name": "goods-manager-svc"
    }
    
    # 带源码提取
    {
      "scip_path": "/path/to/index.scip",
      "project_name": "goods-manager-svc",
      "source_type": "local_path",
      "source_config": {
        "local_source_path": "/path/to/source"
      }
    }
    """,
)
async def ingest_scip_only(
    data: ScipIngestOnlyRequest,
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """
    仅摄取SCIP文件（支持源码配置）

    快速通道：跳过Git clone和SCIP生成，直接使用已有SCIP
    """
    # 验证项目名称
    try:
        validated_project_name = InputValidator.sanitize_log_message(data.project_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid project name: {str(e)}")

    # 验证source_config与source_type匹配
    if data.source_type and not data.source_config:
        raise HTTPException(
            status_code=400, detail="source_config is required when source_type is specified"
        )

    # 验证SCIP文件路径
    if not data.scip_path or not data.scip_path.strip():
        raise HTTPException(status_code=400, detail="scip_path is required and cannot be empty")

    # 生成任务ID
    job_id = str(uuid.uuid4())

    logger.info(
        f"收到SCIP直接摄取请求: job_id={job_id}, "
        f"project={validated_project_name}, scip_path={data.scip_path}"
    )

    # 初始化任务状态
    job_data = {
        "job_id": job_id,
        "project_name": validated_project_name,
        "status": JobStatus.PENDING.value,
        "stage": IngestionStage.PARSING.value,
        "progress": 0,
        "message": "任务已创建,等待解析SCIP",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "write_phase": "prepare",
        "items_total": None,
        "items_done": None,
    }
    job_store.set(job_id, job_data)
    job_store.set_project_active_job(validated_project_name, job_id)
    _mark_snapshot_rebuilding(validated_project_name)

    # 提交Celery任务
    celery_app.send_task(
        "src.ingestion.tasks.ingest_scip_file",
        args=[
            str(data.scip_path),
            validated_project_name,
            data.source_type,
            data.source_config,
        ],
        task_id=job_id,
    )

    return IngestResponse(
        job_id=job_id,
        project_name=validated_project_name,
        status=JobStatus.PENDING,
        message="SCIP直接摄取任务已提交",
    )
