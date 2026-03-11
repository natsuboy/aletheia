"""Wiki 双层缓存 (Redis + 文件系统)"""

import json
from pathlib import Path
from typing import Optional
from loguru import logger

from src.wiki.models import WikiStructure


class WikiCache:
    """双层缓存：Redis (热) + 文件系统 (冷)"""

    def __init__(self, redis_client, cache_dir: str = "data/wikicache", ttl: int = 86400):
        self.redis = redis_client
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl

    def _redis_key(self, project_id: str) -> str:
        return f"wiki:{project_id}"

    def _file_path(self, project_id: str) -> Path:
        return self.cache_dir / f"{project_id}.json"

    async def get(self, project_id: str) -> Optional[WikiStructure]:
        """获取缓存：Redis 优先 -> 文件回退 -> 回填 Redis"""
        # Layer 1: Redis
        try:
            data = await self.redis.get(self._redis_key(project_id))
            if data:
                logger.debug(f"Wiki cache hit (Redis): {project_id}")
                return WikiStructure.model_validate_json(data)
        except Exception as e:
            logger.warning(f"Redis read failed: {e}")

        # Layer 2: 文件系统
        fp = self._file_path(project_id)
        if fp.exists():
            try:
                raw = fp.read_text(encoding="utf-8")
                wiki = WikiStructure.model_validate_json(raw)
                logger.debug(f"Wiki cache hit (file): {project_id}")
                # 回填 Redis
                try:
                    await self.redis.setex(
                        self._redis_key(project_id), self.ttl, raw
                    )
                except Exception:
                    pass
                return wiki
            except Exception as e:
                logger.warning(f"File cache read failed: {e}")

        return None

    async def save(self, project_id: str, wiki: WikiStructure) -> None:
        """写入双层缓存"""
        payload = wiki.model_dump_json()

        # Layer 1: Redis
        try:
            await self.redis.setex(self._redis_key(project_id), self.ttl, payload)
            logger.debug(f"Wiki saved to Redis: {project_id}")
        except Exception as e:
            logger.warning(f"Redis write failed: {e}")

        # Layer 2: 文件系统
        try:
            self._file_path(project_id).write_text(payload, encoding="utf-8")
            logger.debug(f"Wiki saved to file: {project_id}")
        except Exception as e:
            logger.warning(f"File write failed: {e}")

    async def invalidate(self, project_id: str) -> None:
        """删除双层缓存"""
        # Redis
        try:
            await self.redis.delete(self._redis_key(project_id))
        except Exception as e:
            logger.warning(f"Redis delete failed: {e}")

        # 文件
        fp = self._file_path(project_id)
        if fp.exists():
            try:
                fp.unlink()
            except Exception as e:
                logger.warning(f"File delete failed: {e}")

        logger.info(f"Wiki cache invalidated: {project_id}")
