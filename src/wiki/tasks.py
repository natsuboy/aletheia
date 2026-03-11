import asyncio
from pathlib import Path
from celery import shared_task
from loguru import logger


@shared_task(bind=True, name="src.wiki.tasks.generate_wiki")
def generate_wiki(self, project_id: str, force: bool = False):
    """Wiki 生成 Celery 任务"""
    job_id = self.request.id
    logger.info(f"Starting wiki generation task {job_id} for project {project_id}")

    from src.backend.job_store import job_store

    try:
        job_store.update(job_id, {
            "status": "running",
            "message": "Wiki 生成中…",
            "progress": 10,
        })

        # 组装 WikiGenerator 依赖
        from src.backend.config import get_settings
        from src.graph.client import GraphClient
        from src.rag.llm_client import LLMClient
        from src.rag.retriever import HybridRetriever
        from src.rag.vector_store import VectorStore, EmbeddingGenerator
        from src.rag.graph_retriever import GraphRetriever
        from src.rag.intent_classifier import IntentClassifier
        from src.wiki.structure_analyzer import WikiStructureAnalyzer
        from src.wiki.content_generator import WikiContentGenerator
        from src.wiki.cache import WikiCache
        from src.wiki.generator import WikiGenerator
        import redis as _redis

        settings = get_settings()
        graph_client = GraphClient()
        graph_client.connect()
        llm_client = LLMClient(model=settings.default_llm_model)
        vector_store = VectorStore()
        pure_project_id = project_id.removeprefix("project:")
        store_path = Path("/data/aletheia") / f"{pure_project_id}.faiss"
        if store_path.exists():
            vector_store.load(str(store_path))
            logger.info(f"Loaded wiki vector store: {store_path}")
        else:
            logger.warning(f"Vector store not found for wiki project {project_id}: {store_path}")
        retriever = HybridRetriever(
            vector_store=vector_store,
            embedding_generator=EmbeddingGenerator(model=settings.embedding_model),
            graph_retriever=GraphRetriever(graph_client),
            intent_classifier=IntentClassifier(),
        )
        redis_client = _redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            decode_responses=True,
        )

        analyzer = WikiStructureAnalyzer(graph_client, llm_client, project_id)
        content_gen = WikiContentGenerator(llm_client, graph_client, retriever)
        cache = WikiCache(redis_client=redis_client)
        generator = WikiGenerator(analyzer, content_gen, cache)

        if force:
            from src.graph.cluster_service import ClusterService

            async def _run_with_clustering():
                cluster_svc = ClusterService(graph_client)
                await cluster_svc.cluster_project(project_id)
                return await generator.generate(project_id)

            wiki = asyncio.run(_run_with_clustering())
        else:
            wiki = asyncio.run(generator.generate(project_id))

        quality = {
            "total_pages": len(wiki.pages),
            "pages_with_content": sum(1 for p in wiki.pages.values() if p.content and not p.content.startswith("(Generation failed:")),
            "failed_pages": sum(1 for p in wiki.pages.values() if p.content and p.content.startswith("(Generation failed:")),
            "empty_pages": sum(1 for p in wiki.pages.values() if not p.content),
            "avg_content_length": int(sum(len(p.content) for p in wiki.pages.values()) / max(len(wiki.pages), 1)),
            "total_mermaid_diagrams": sum(len(p.mermaid_diagrams) for p in wiki.pages.values()),
            "sections_count": len(wiki.sections),
        }

        job_store.update(job_id, {
            "status": "completed",
            "progress": 100,
            "message": "Wiki 生成完成",
            "quality_summary": quality,
        })
        logger.info(f"Wiki generation task {job_id} completed")
        return {"status": "completed", "job_id": job_id}

    except Exception as e:
        logger.error(f"Wiki generation task {job_id} failed: {e}")
        job_store.update(job_id, {
            "status": "failed",
            "error": str(e),
            "failure_class": "wiki_generation_failed",
            "message": f"Wiki 生成失败: {e}",
        })
        raise

    finally:
        current = job_store.get_project_wiki_job(project_id)
        if current == job_id:
            job_store.clear_project_wiki_job(project_id)
        graph_client.close()
