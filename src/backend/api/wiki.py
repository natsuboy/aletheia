"""Wiki API 端点"""

import uuid
from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from loguru import logger
from pydantic import BaseModel, Field

from src.backend.security import InputValidator
from src.models.api import JobStatus
from src.backend.celery_app import celery_app
from src.backend.job_store import job_store
from src.wiki.models import WikiStructure
from src.wiki.cache import WikiCache
from src.wiki.structure_analyzer import WikiStructureAnalyzer
from src.wiki.content_generator import WikiContentGenerator
from src.wiki.generator import WikiGenerator

router = APIRouter(prefix="/api/wiki", tags=["wiki"])


# ------------------------------------------------------------------
# Request / Response models
# ------------------------------------------------------------------

class WikiGenerateRequest(BaseModel):
    project_id: str = Field(..., min_length=1, max_length=100)
    force: bool = Field(default=False, description="强制重新生成（先重新聚类）")


class WikiGenerateResponse(BaseModel):
    job_id: str
    project_id: str
    status: JobStatus
    message: str


class WikiExportRequest(BaseModel):
    project_id: str = Field(..., min_length=1, max_length=100)
    format: str = Field(default="markdown", description="Export format: markdown | json")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _get_wiki_cache(request: Request) -> WikiCache:
    """从 app.state 获取 WikiCache 实例"""
    redis = request.app.state.redis
    return WikiCache(redis_client=redis)


def _get_wiki_generator(request: Request, project_id: str) -> WikiGenerator:
    """从 app.state 组装 WikiGenerator"""
    rag = request.app.state.rag_components
    graph_client = rag["graph_client"]
    llm_client = rag["llm_client"]
    retriever = rag["retriever"]
    redis = request.app.state.redis

    analyzer = WikiStructureAnalyzer(graph_client, llm_client, project_id)
    content_gen = WikiContentGenerator(llm_client, graph_client, retriever)
    cache = WikiCache(redis_client=redis)
    return WikiGenerator(analyzer, content_gen, cache)


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------

@router.get("/diagnose/{project_id}")
async def diagnose_wiki(project_id: str, request: Request):
    """诊断 Wiki 生成环境：图谱、聚类、缓存、任务状态"""
    try:
        project_id = InputValidator.validate_project_id(project_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    graph_client = request.app.state.graph_client
    result: Dict[str, Any] = {}

    # 1. 图谱诊断
    try:
        nodes = graph_client.execute_query(
            "MATCH (n) WHERE n.project_id = $pid RETURN count(n) AS cnt",
            {"pid": project_id},
        )
        edges = graph_client.execute_query(
            "MATCH (n)-[r]->() WHERE n.project_id = $pid RETURN count(r) AS cnt",
            {"pid": project_id},
        )
        has_cid = graph_client.execute_query(
            "MATCH (n) WHERE n.project_id = $pid AND n.community_id IS NOT NULL RETURN count(n) AS cnt",
            {"pid": project_id},
        )
        result["graph"] = {
            "node_count": nodes[0]["cnt"] if nodes else 0,
            "edge_count": edges[0]["cnt"] if edges else 0,
            "has_community_ids": (has_cid[0]["cnt"] if has_cid else 0) > 0,
        }
    except Exception as e:
        result["graph"] = {"error": str(e)}

    # 2. 聚类诊断
    try:
        comms = graph_client.execute_query(
            "MATCH (n) WHERE n.project_id = $pid AND n.community_id IS NOT NULL "
            "RETURN n.community_id AS cid, count(n) AS size ORDER BY size DESC",
            {"pid": project_id},
        )
        result["clustering"] = {
            "community_count": len(comms),
            "community_sizes": {r["cid"]: r["size"] for r in comms},
        }
    except Exception as e:
        result["clustering"] = {"error": str(e)}

    # 3. 缓存诊断
    cache = _get_wiki_cache(request)
    try:
        redis_exists = await request.app.state.redis.exists(f"wiki:{project_id}")
        file_path = cache._file_path(project_id)
        file_exists = file_path.exists()
        result["cache"] = {
            "redis_exists": bool(redis_exists),
            "file_exists": file_exists,
            "file_size_bytes": file_path.stat().st_size if file_exists else 0,
        }
    except Exception as e:
        result["cache"] = {"error": str(e)}

    # 4. 任务状态
    job_id = job_store.get_project_wiki_job(project_id)
    if job_id:
        job = job_store.get(job_id)
        result["job"] = {
            "last_job_id": job_id,
            "last_status": job.get("status") if job else None,
            "last_message": job.get("message") if job else None,
        }
    else:
        result["job"] = {"last_job_id": None}

    # 5. Wiki 质量（如果缓存存在）
    wiki = await cache.get(project_id)
    if wiki:
        result["wiki_quality"] = {
            "page_count": len(wiki.pages),
            "sections_count": len(wiki.sections),
            "empty_pages": sum(1 for p in wiki.pages.values() if not p.content),
            "failed_pages": sum(1 for p in wiki.pages.values() if p.content and p.content.startswith("(Generation failed:")),
            "avg_content_length": int(sum(len(p.content) for p in wiki.pages.values()) / max(len(wiki.pages), 1)),
            "mermaid_count": sum(len(p.mermaid_diagrams) for p in wiki.pages.values()),
        }

    return result

@router.post("/generate", response_model=WikiGenerateResponse)
async def generate_wiki(data: WikiGenerateRequest, request: Request):
    """触发 Wiki 生成（异步 Celery 任务），支持幂等去重"""
    try:
        project_id = InputValidator.validate_project_id(data.project_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 去重：检查是否已有活跃的 wiki 生成任务
    existing_job_id = job_store.get_project_wiki_job(project_id)
    if existing_job_id:
        existing_job = job_store.get(existing_job_id)
        if existing_job and existing_job.get("status") in (
            JobStatus.PENDING.value,
            JobStatus.RUNNING.value,
        ):
            logger.info(f"Wiki generation already active: project={project_id}, job={existing_job_id}")
            return WikiGenerateResponse(
                job_id=existing_job_id,
                project_id=project_id,
                status=JobStatus(existing_job["status"]),
                message="Wiki 生成任务进行中",
            )
        # 旧任务已结束，清除映射
        job_store.clear_project_wiki_job(project_id)

    # force 模式：先清除缓存
    if data.force:
        cache = _get_wiki_cache(request)
        await cache.invalidate(project_id)

    job_id = str(uuid.uuid4())
    logger.info(f"Wiki generation requested: project={project_id}, job={job_id}")

    job_store.set(job_id, {
        "job_id": job_id,
        "project_name": project_id,
        "status": JobStatus.PENDING.value,
        "stage": "wiki_generation",
        "progress": 0,
        "message": "Wiki 生成任务已提交",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    })
    job_store.set_project_wiki_job(project_id, job_id)

    celery_app.send_task(
        "src.wiki.tasks.generate_wiki",
        args=[project_id, data.force],
        task_id=job_id,
        queue="wiki",
    )

    return WikiGenerateResponse(
        job_id=job_id,
        project_id=project_id,
        status=JobStatus.PENDING,
        message="Wiki 生成任务已提交",
    )


@router.get("/generate/active/{project_id}", response_model=WikiGenerateResponse)
async def get_active_wiki_job(project_id: str):
    """查询项目活跃的 wiki 生成任务"""
    try:
        project_id = InputValidator.validate_project_id(project_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    job_id = job_store.get_project_wiki_job(project_id)
    if not job_id:
        raise HTTPException(status_code=404, detail="No active wiki job")

    job = job_store.get(job_id)
    if not job or job.get("status") not in (
        JobStatus.PENDING.value,
        JobStatus.RUNNING.value,
    ):
        job_store.clear_project_wiki_job(project_id)
        raise HTTPException(status_code=404, detail="No active wiki job")

    return WikiGenerateResponse(
        job_id=job_id,
        project_id=project_id,
        status=JobStatus(job["status"]),
        message=job.get("message", ""),
    )


@router.get("/{project_id}")
async def get_wiki(project_id: str, request: Request):
    """获取已缓存的 Wiki"""
    try:
        project_id = InputValidator.validate_project_id(project_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    cache = _get_wiki_cache(request)
    wiki = await cache.get(project_id)
    if not wiki:
        raise HTTPException(status_code=404, detail=f"Wiki not found for project {project_id}")
    return wiki.model_dump()


@router.get("/{project_id}/page/{page_id}")
async def get_wiki_page(project_id: str, page_id: str, request: Request):
    """获取单个 Wiki 页面"""
    try:
        project_id = InputValidator.validate_project_id(project_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    cache = _get_wiki_cache(request)
    wiki = await cache.get(project_id)
    if not wiki:
        raise HTTPException(status_code=404, detail=f"Wiki not found for project {project_id}")
    page = wiki.pages.get(page_id)
    if not page:
        raise HTTPException(status_code=404, detail=f"Page {page_id} not found")
    return page.model_dump()


@router.delete("/{project_id}")
async def invalidate_wiki(project_id: str, request: Request):
    """删除项目 Wiki 缓存"""
    try:
        project_id = InputValidator.validate_project_id(project_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    cache = _get_wiki_cache(request)
    await cache.invalidate(project_id)
    return {"message": f"Wiki cache invalidated for project {project_id}"}


@router.post("/export")
async def export_wiki(data: WikiExportRequest, request: Request):
    """导出 Wiki 为 Markdown 或 JSON"""
    try:
        project_id = InputValidator.validate_project_id(data.project_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    cache = _get_wiki_cache(request)
    wiki = await cache.get(project_id)
    if not wiki:
        raise HTTPException(
            status_code=404,
            detail=f"Wiki not found for project {project_id}",
        )

    if data.format == "json":
        return wiki.model_dump()

    # Markdown export
    lines: list[str] = [f"# {wiki.title}\n", wiki.description, ""]
    for section_id in wiki.root_sections:
        section = wiki.sections.get(section_id)
        if not section:
            continue
        lines.append(f"## {section.title}\n")
        for page_id in section.pages:
            page = wiki.pages.get(page_id)
            if not page:
                continue
            lines.append(f"### {page.title}\n")
            lines.append(page.content)
            for diagram in page.mermaid_diagrams:
                lines.append(f"\n```mermaid\n{diagram}\n```\n")
            lines.append("")

    return {"format": "markdown", "content": "\n".join(lines)}
