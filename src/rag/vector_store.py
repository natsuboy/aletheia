"""向量存储和嵌入生成"""
import asyncio
from typing import List, Dict, Any, Optional
import pickle
import numpy as np
import faiss
from openai import AsyncOpenAI
from loguru import logger

from src.backend.config import get_settings


class EmbeddingGenerator:
    """嵌入生成器 (使用 OpenAI API)"""
    MAX_INPUT_BATCH_SIZE = 64

    def __init__(self, model: str = "text-embedding-3-small"):
        """
        初始化嵌入生成器

        Args:
            model: OpenAI 嵌入模型名称
        """
        self.model = model

        # 根据模型设置维度
        if "bge-m3" in model.lower():
            self.dimension = 1024  # BAAI/bge-m3 的维度
        else:
            self.dimension = 1536  # text-embedding-3-small 的维度

        settings = get_settings()

        # 使用独立的嵌入模型配置，如果没有则回退到 OpenAI 配置
        api_key = settings.embedding_api_key or settings.openai_api_key
        base_url = settings.embedding_base_url or settings.openai_base_url

        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        self.client = AsyncOpenAI(**client_kwargs)

    async def generate(self, texts: List[str]) -> List[List[float]]:
        """生成文本嵌入，带 timeout 和指数退避重试"""
        if not texts:
            return []

        if len(texts) > self.MAX_INPUT_BATCH_SIZE:
            embeddings: List[List[float]] = []
            for i in range(0, len(texts), self.MAX_INPUT_BATCH_SIZE):
                chunk = texts[i:i + self.MAX_INPUT_BATCH_SIZE]
                chunk_embeddings = await self.generate(chunk)
                embeddings.extend(chunk_embeddings)
            return embeddings

        last_err = None
        for attempt in range(3):
            try:
                response = await self.client.embeddings.create(
                    model=self.model,
                    input=texts,
                    timeout=60.0,
                )
                return [item.embedding for item in response.data]
            except Exception as e:
                last_err = e
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
        logger.error(f"Failed to generate embeddings: {last_err}")
        raise last_err


class VectorStore:
    """FAISS 向量存储"""

    def __init__(self, dimension: int = 1536):
        """
        初始化向量存储

        Args:
            dimension: 向量维度
        """
        self.dimension = dimension

        # 创建 FAISS 索引 (使用 L2 距离)
        self.index = faiss.IndexFlatL2(dimension)

        # 存储 ID 映射
        self.id_to_index: Dict[str, int] = {}
        self.index_to_id: Dict[int, str] = {}
        self.metadata: Dict[str, Dict[str, Any]] = {}

        self._next_index = 0

        logger.info(f"Initialized FAISS index with dimension {dimension}")

    def add(
        self,
        vectors: np.ndarray,
        ids: List[str],
        metadata: Optional[List[Dict[str, Any]]] = None
    ):
        """
        添加向量到索引

        Args:
            vectors: 向量数组 (shape: [n, dimension])
            ids: 向量 ID 列表
            metadata: 元数据列表 (可选)
        """
        if vectors.shape[0] != len(ids):
            raise ValueError("vectors and ids must have same length")

        if vectors.shape[1] != self.dimension:
            raise ValueError(f"vectors must have dimension {self.dimension}")

        # 确保是 float32 类型
        vectors = vectors.astype('float32')

        # 添加到 FAISS 索引
        self.index.add(vectors)

        # 更新 ID 映射
        for i, vec_id in enumerate(ids):
            idx = self._next_index + i
            self.id_to_index[vec_id] = idx
            self.index_to_id[idx] = vec_id

            if metadata and i < len(metadata):
                self.metadata[vec_id] = metadata[i]

        self._next_index += len(ids)

        logger.info(f"Added {len(ids)} vectors to index")

    def search(
        self,
        query_vectors: np.ndarray,
        k: int = 10,
        project_id: Optional[str] = None,
    ) -> List[List[Dict[str, Any]]]:
        """
        搜索最相似的向量

        Args:
            query_vectors: 查询向量 (shape: [n_queries, dimension])
            k: 返回的最近邻数量
            project_id: 可选，按项目过滤结果（基于 metadata.project）

        Returns:
            结果列表,每个查询对应一个结果列表
        """
        if query_vectors.shape[1] != self.dimension:
            raise ValueError(f"query_vectors must have dimension {self.dimension}")

        # 确保是 float32 类型
        query_vectors = query_vectors.astype('float32')

        # 搜索。项目过滤时扩大召回候选，再在内存中过滤。
        search_k = k
        if project_id:
            search_k = min(max(k * 8, k), max(self.index.ntotal, k))
        distances, indices = self.index.search(query_vectors, search_k)

        # 构建结果
        results = []
        for i in range(len(query_vectors)):
            query_results = []
            for j in range(search_k):
                idx = int(indices[i][j])
                if idx == -1:  # FAISS 返回 -1 表示没有足够的结果
                    break

                vec_id = self.index_to_id.get(idx)
                if vec_id:
                    vec_metadata = self.metadata.get(vec_id, {})
                    if project_id and vec_metadata.get("project") != project_id:
                        continue
                    result = {
                        "id": vec_id,
                        "distance": float(distances[i][j]),
                        "metadata": vec_metadata,
                    }
                    query_results.append(result)
                    if len(query_results) >= k:
                        break

            results.append(query_results)

        logger.info(f"Searched {len(query_vectors)} queries, found {len(results)} result sets")

        return results

    def count(self) -> int:
        """返回索引中的向量数量"""
        return self.index.ntotal

    def save(self, filepath: str):
        """保存索引和元数据到文件"""
        # 保存 FAISS 索引
        faiss.write_index(self.index, filepath)

        # 保存元数据
        metadata_path = filepath + ".meta"
        with open(metadata_path, 'wb') as f:
            pickle.dump({
                'id_to_index': self.id_to_index,
                'index_to_id': self.index_to_id,
                'metadata': self.metadata,
                '_next_index': self._next_index,
                'dimension': self.dimension
            }, f)
        logger.info(f"Saved index and metadata to {filepath}")

    def load(self, filepath: str, replace: bool = True):
        """从文件加载索引和元数据"""
        # 加载元数据
        metadata_path = filepath + ".meta"
        with open(metadata_path, 'rb') as f:
            data = pickle.load(f)
            loaded_dimension = data['dimension']

        if replace:
            # 覆盖模式（保持旧行为）
            self.index = faiss.read_index(filepath)
            self.id_to_index = data['id_to_index']
            self.index_to_id = data['index_to_id']
            self.metadata = data['metadata']
            self._next_index = data['_next_index']
            self.dimension = loaded_dimension
            logger.info(f"Loaded index and metadata from {filepath} (replace=True)")
            return

        # 合并模式：将文件中的向量与元数据增量并入当前索引
        loaded_index = faiss.read_index(filepath)
        if loaded_dimension != self.dimension:
            raise ValueError(
                f"Dimension mismatch when merging index: loaded={loaded_dimension}, current={self.dimension}"
            )

        if loaded_index.ntotal == 0:
            logger.info(f"Loaded empty index from {filepath}, skip merge")
            return

        loaded_vectors = loaded_index.reconstruct_n(0, loaded_index.ntotal)
        loaded_index_to_id = data['index_to_id']
        loaded_metadata = data['metadata']

        merge_ids: List[str] = []
        merge_metas: List[Dict[str, Any]] = []
        merge_indices: List[int] = []
        for i in range(loaded_index.ntotal):
            vec_id = loaded_index_to_id.get(i)
            if not vec_id:
                continue
            if vec_id in self.id_to_index:
                # 冲突时跳过，避免不同项目/版本互相覆盖
                continue
            merge_indices.append(i)
            merge_ids.append(vec_id)
            merge_metas.append(loaded_metadata.get(vec_id, {}))

        if not merge_ids:
            logger.info(f"No new vectors to merge from {filepath}")
            return

        self.add(loaded_vectors[merge_indices], merge_ids, merge_metas)
        logger.info(f"Merged {len(merge_ids)} vectors from {filepath}")
