"""混合检索器 (向量 + 图谱)"""
from typing import List, Dict, Any
from dataclasses import dataclass, field
import asyncio
import uuid
import numpy as np
from loguru import logger

from src.rag.vector_store import VectorStore, EmbeddingGenerator
from src.rag.graph_retriever import GraphRetriever, GraphContext
from src.rag.intent_classifier import IntentClassifier, QueryIntent, IntentClassification
from src.graph.cache import QueryCache


@dataclass
class RetrievalResult:
    """检索结果"""
    contexts: List[Dict[str, Any]] = field(default_factory=list)
    graph_context: GraphContext = field(default_factory=GraphContext)
    intent: QueryIntent = QueryIntent.IMPLEMENTATION
    metadata: Dict[str, Any] = field(default_factory=dict)


class HybridRetriever:
    """混合检索器 (向量 + 图谱)"""

    def __init__(
        self,
        vector_store: VectorStore,
        embedding_generator: EmbeddingGenerator,
        graph_retriever: GraphRetriever,
        intent_classifier: IntentClassifier,
        query_cache: QueryCache = None
    ):
        """
        初始化混合检索器

        Args:
            vector_store: 向量存储
            embedding_generator: 嵌入生成器
            graph_retriever: 图谱检索器
            intent_classifier: 意图分类器
        """
        self.vector_store = vector_store
        self.embedding_generator = embedding_generator
        self.graph_retriever = graph_retriever
        self.intent_classifier = intent_classifier
        self.query_cache = query_cache or QueryCache()

    async def retrieve(
        self,
        query: str,
        project_id: str,
        k: int = 10
    ) -> RetrievalResult:
        """
        混合检索 (向量 + 图谱)

        Args:
            query: 用户查询
            project_id: 项目 ID
            k: 返回结果数量

        Returns:
            检索结果
        """
        # 统一 project id 规范：
        # - graph_project_id: project:{name}
        # - storage_project_id: name
        graph_project_id = project_id if project_id.startswith("project:") else f"project:{project_id}"
        storage_project_id = project_id.removeprefix("project:")

        retrieval_trace_id = str(uuid.uuid4())
        cached = self.query_cache.get(query, storage_project_id, k)
        if cached is not None:
            return RetrievalResult(
                contexts=cached,
                metadata={"cache_hit": True, "retrieval_trace_id": retrieval_trace_id},
            )

        # Step 1: 意图分类 (添加异常处理)
        try:
            intent_result = self.intent_classifier.classify(query)
            logger.info(f"Query intent: {intent_result.intent.value}")
        except Exception as e:
            logger.warning(f"Intent classification failed: {e}, using default weights")
            intent_result = IntentClassification(
                intent=QueryIntent.IMPLEMENTATION,
                confidence=0.3,
                vector_weight=0.6,
                graph_weight=0.4
            )

        # Step 2: 并行检索
        async def _vector_search() -> List[Dict[str, Any]]:
            try:
                query_embedding = await self.embedding_generator.generate([query])
                query_vector = np.array(query_embedding).astype('float32')
                vector_results = self.vector_store.search(
                    query_vector, k=k * 2, project_id=storage_project_id
                )
                return vector_results[0] if vector_results else []
            except Exception as e:
                logger.error(f"Vector search failed: {e}")
                return []

        async def _graph_search() -> GraphContext:
            try:
                return await self.graph_retriever.retrieve(
                    query=query, project_id=graph_project_id
                )
            except Exception as e:
                logger.error(f"Graph retrieval failed: {e}")
                return GraphContext()

        vector_contexts, graph_context = await asyncio.gather(
            _vector_search(), _graph_search()
        )

        # Step 3: 融合上下文
        combined_contexts = self._fuse_contexts(
            vector_contexts=vector_contexts,
            graph_context=graph_context,
            vector_weight=intent_result.vector_weight,
            graph_weight=intent_result.graph_weight,
            k=k
        )

        logger.info(
            f"Retrieved {len(combined_contexts)} contexts "
            f"(vector={len(vector_contexts)}, graph_entities={len(graph_context.entities)})"
        )

        self.query_cache.set(query, storage_project_id, k, combined_contexts)

        return RetrievalResult(
            contexts=combined_contexts,
            graph_context=graph_context,
            intent=intent_result.intent,
            metadata={
                "cache_hit": False,
                "retrieval_trace_id": retrieval_trace_id,
                "vector_weight": intent_result.vector_weight,
                "graph_weight": intent_result.graph_weight,
                "confidence": intent_result.confidence
            }
        )

    def _fuse_contexts(
        self,
        vector_contexts: List[Dict[str, Any]],
        graph_context: GraphContext,
        vector_weight: float,
        graph_weight: float,
        k: int
    ) -> List[Dict[str, Any]]:
        """
        融合向量和图谱上下文

        Args:
            vector_contexts: 向量检索结果
            graph_context: 图谱上下文
            vector_weight: 向量权重
            graph_weight: 图谱权重
            k: 返回数量

        Returns:
            融合后的上下文列表
        """
        # Reciprocal Rank Fusion (RRF) with configurable weights
        # RRF score = weight * 1/(rrf_k + rank)
        rrf_k = 60  # standard RRF constant
        scored: Dict[str, Dict[str, Any]] = {}

        # 向量结果按距离排序（距离越小排名越前）
        try:
            sorted_vec = sorted(vector_contexts[:k * 2], key=lambda c: c.get("distance", 1.0))
            for rank, ctx in enumerate(sorted_vec):
                text = ctx.get("metadata", {}).get("text", "")
                key = text[:200] if text else f"vec_{rank}"
                rrf_score = vector_weight * (1.0 / (rrf_k + rank + 1))
                scored[key] = {
                    "text": text,
                    "source": "vector",
                    "score": rrf_score,
                    "metadata": ctx.get("metadata", {}),
                }
        except Exception as e:
            logger.error(f"Error processing vector contexts: {e}")

        # 图谱结果按 RRF 排名
        try:
            for rank, entity in enumerate(graph_context.entities[:k]):
                text = f"Entity: {entity.get('name')} (type: {entity.get('type')})"
                key = text[:200]
                rrf_score = graph_weight * (1.0 / (rrf_k + rank + 1))
                if key in scored:
                    scored[key]["score"] += rrf_score
                else:
                    scored[key] = {
                        "text": text,
                        "source": "graph",
                        "score": rrf_score,
                        "metadata": entity,
                    }
        except Exception as e:
            logger.error(f"Error processing graph contexts: {e}")

        results = sorted(scored.values(), key=lambda x: x["score"], reverse=True)
        return results[:k]
