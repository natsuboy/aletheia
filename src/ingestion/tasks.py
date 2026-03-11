import asyncio
from celery import shared_task
from src.ingestion.service import IngestionService
from src.ingestion.provider import SourceProviderFactory
from src.backend.job_store import job_store
from loguru import logger
from pathlib import Path
from typing import Optional, Dict, Any


def _normalize_source_config(source_type: str, source_config: Dict[str, Any]) -> Dict[str, Any]:
    """统一 source_config 键名，兼容新旧 API 字段。"""
    cfg = dict(source_config or {})
    if source_type == "local_path":
        if "path" not in cfg and "local_source_path" in cfg:
            cfg["path"] = cfg["local_source_path"]
    elif source_type == "zip_file":
        if "zip_path" not in cfg and "source_zip_path" in cfg:
            cfg["zip_path"] = cfg["source_zip_path"]
    elif source_type == "gitlab_repo":
        if "repo_url" not in cfg and "gitlab_repo" in cfg:
            cfg["repo_url"] = cfg["gitlab_repo"]
        if "branch" not in cfg and "gitlab_branch" in cfg:
            cfg["branch"] = cfg["gitlab_branch"]
        if "token" not in cfg and "gitlab_token" in cfg:
            cfg["token"] = cfg["gitlab_token"]
    return cfg


@shared_task(bind=True, name="src.ingestion.tasks.ingest_repository")
def ingest_repository(
    self,
    repo_url: str,
    language: str,
    project_name: str,
    branch: str = "main",
):
    """
    摄取仓库任务
    """
    job_id = self.request.id
    logger.info(f"Starting ingestion task {job_id} for {repo_url}")

    # 运行异步服务方法
    try:
        service = IngestionService()
        asyncio.run(
            service.ingest(
                repo_url=repo_url,
                language=language,
                project_name=project_name,
                branch=branch,
                job_id=job_id,
            )
        )
        logger.info(f"Ingestion task {job_id} completed successfully")
        return {"status": "completed", "job_id": job_id}
    except Exception as e:
        logger.error(f"Ingestion task {job_id} failed: {e}")
        from src.backend.job_store import job_store
        job_store.update(job_id, {
            "status": "failed",
            "stage": "failed",
            "error": str(e),
            "failure_class": "ingestion_repository_failed",
            "message": f"摄取失败: {e}",
        })
        raise e


@shared_task(bind=True, name="src.ingestion.tasks.ingest_scip_file")
def ingest_scip_file_task(
    self,
    scip_file_path: str,
    project_name: str,
    source_type: Optional[str] = None,
    source_config: Optional[Dict[str, Any]] = None,
):
    """
    直接摄取SCIP文件的Celery任务

    支持可选的源码提供者配置
    """
    job_id = self.request.id
    logger.info(f"Starting SCIP ingestion task {job_id}")

    try:
        # 创建源码提供者（如果需要）
        source_root = None

        if source_type and source_config:
            normalized_config = _normalize_source_config(source_type, source_config)
            if source_type == "local_path":
                provider = SourceProviderFactory.create(source_type, normalized_config)
                source_root = provider.root_path
            elif source_type == "gitlab_repo":
                provider = SourceProviderFactory.create(source_type, normalized_config)
                asyncio.run(provider.clone())
                source_root = provider._cloned_path
            elif source_type == "zip_file":
                # zip_file 目前用于按文件读取源码；暂不提供稳定 source_root 目录。
                SourceProviderFactory.create(source_type, normalized_config)
            logger.info(f"Source code obtained: {source_root}")

        # 运行服务（注意：scip_file_path需要是Path类型，转换为Path对象）
        from pathlib import Path

        service = IngestionService()
        service.ingest_scip_file(
            scip_file_path=Path(scip_file_path),
            project_name=project_name,
            source_root=source_root,
            job_id=job_id,
        )
        logger.info(f"SCIP ingestion task {job_id} completed successfully")
        return {"status": "completed", "job_id": job_id}
    except Exception as e:
        logger.error(f"SCIP ingestion task {job_id} failed: {e}")
        from src.backend.job_store import job_store
        job_store.update(job_id, {
            "status": "failed",
            "stage": "failed",
            "error": str(e),
            "failure_class": "ingestion_scip_failed",
            "message": f"摄取失败: {e}",
        })
        raise e


@shared_task(bind=True, name="src.ingestion.tasks.delete_project")
def delete_project_task(self, project_name: str):
    """删除项目的 Celery 任务"""
    job_id = self.request.id
    job_store.update(job_id, {
        "status": "running", "stage": "deleting",
        "progress": 10, "message": f"正在删除项目 {project_name}...",
    })
    try:
        service = IngestionService()
        service.clear_project_data(project_name)
        job_store.update(job_id, {
            "status": "completed", "stage": "completed",
            "progress": 100, "message": f"项目 {project_name} 已删除",
        })
        return {"status": "completed", "job_id": job_id}
    except Exception as e:
        logger.error(f"Delete project task {job_id} failed: {e}")
        job_store.update(job_id, {
            "status": "failed", "stage": "failed",
            "error": str(e), "failure_class": "project_delete_failed", "message": f"删除失败: {e}",
        })
        raise
