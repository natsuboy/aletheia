"""FastAPI 应用主入口"""
import asyncio
import json
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
import redis.asyncio as aioredis

from src.backend.config import get_settings
from src.backend.middleware.error_handler import error_handler_middleware
from src.backend.middleware.logging import logging_middleware
from src.backend.api.health import router as health_router
from src.backend.api.ingest import router as ingest_router
from src.backend.api.graph import router as graph_router
from src.backend.api.chat import router as chat_router
from src.backend.api.doc import router as doc_router
from src.backend.api.wiki import router as wiki_router
from src.backend.api.research import router as research_router
from src.backend.api.nav import router as nav_router
from src.rag.conversation import ConversationMemory


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("Starting Aletheia API server...")
    settings = get_settings()
    logger.info(f"Environment: {settings.app_env}")

    # Redis async client for pub/sub
    app.state.redis = aioredis.Redis(
        host=settings.redis_host, port=settings.redis_port, db=settings.redis_db
    )

    # 初始化 RAG 组件单例
    from src.graph import GraphClient
    from src.rag import (
        VectorStore, EmbeddingGenerator, GraphRetriever,
        IntentClassifier, HybridRetriever, LLMClient, PromptBuilder
    )
    graph_client = GraphClient()
    graph_client.connect()
    app.state.graph_client = graph_client
    embedding_gen = EmbeddingGenerator(model=settings.embedding_model)
    vector_store = VectorStore(dimension=embedding_gen.dimension)
    faiss_dir = Path("/data/aletheia")
    if faiss_dir.exists():
        for faiss_file in sorted(faiss_dir.glob("*.faiss")):
            try:
                vector_store.load(str(faiss_file), replace=False)
                logger.info(f"Loaded vector store from {faiss_file}")
            except Exception as e:
                logger.warning(f"Failed to load vector store {faiss_file}: {e}")
    app.state.rag_components = {
        "retriever": HybridRetriever(
            vector_store=vector_store,
            embedding_generator=embedding_gen,
            graph_retriever=GraphRetriever(graph_client),
            intent_classifier=IntentClassifier(),
        ),
        "llm_client": LLMClient(model=settings.default_llm_model),
        "prompt_builder": PromptBuilder(max_context_tokens=settings.max_context_tokens),
        "graph_client": graph_client,
    }

    # 初始化会话记忆
    app.state.conversation_memory = ConversationMemory(
        redis_client=app.state.redis,
        ttl=settings.conversation_ttl,
        max_turns=settings.conversation_max_turns,
    )

    yield

    graph_client.close()
    await app.state.redis.aclose()
    logger.info("Shutting down Aletheia API server...")


def create_app() -> FastAPI:
    """创建 FastAPI 应用"""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Code intelligence platform with SCIP-powered knowledge graph",
        lifespan=lifespan,
    )

    # CORS 中间件
    origins = settings.cors_origins.split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 自定义中间件
    app.middleware("http")(logging_middleware)
    app.middleware("http")(error_handler_middleware)

    # 注册路由
    app.include_router(health_router)
    app.include_router(ingest_router)
    app.include_router(graph_router)
    app.include_router(chat_router)
    app.include_router(doc_router)
    app.include_router(wiki_router)
    app.include_router(research_router)
    app.include_router(nav_router)

    @app.websocket("/ws/{project_id}")
    async def ws_progress(websocket: WebSocket, project_id: str):
        """WebSocket 实时进度推送，订阅 Redis 频道 ingestion:{project_id}"""
        await websocket.accept()
        pubsub = app.state.redis.pubsub()
        channel = f"ingestion:{project_id}"
        await pubsub.subscribe(channel)

        # 补发当前状态，解决 WebSocket 建立前消息丢失问题
        try:
            active_job_id = await app.state.redis.get(f"project-active-job:{project_id}")
            if active_job_id:
                job_id_str = active_job_id if isinstance(active_job_id, str) else active_job_id.decode()
                raw = await app.state.redis.get(f"job:{job_id_str}")
                if raw:
                    await websocket.send_text(raw if isinstance(raw, str) else raw.decode())
        except Exception as e:
            logger.warning(f"Failed to send initial state for {project_id}: {e}")

        try:
            while True:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg and msg["type"] == "message":
                    await websocket.send_text(msg["data"] if isinstance(msg["data"], str) else msg["data"].decode())
                await asyncio.sleep(0.1)
        except WebSocketDisconnect:
            pass
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

    return app


# 创建应用实例
app = create_app()
