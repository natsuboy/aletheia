"""会话记忆管理器 — Redis-backed 多轮对话状态"""

import json
import time
from dataclasses import dataclass, field, asdict
from typing import List, Optional

import redis.asyncio as aioredis
from loguru import logger


@dataclass
class DialogTurn:
    """单轮对话"""
    user_query: str
    assistant_response: str
    timestamp: float = field(default_factory=time.time)
    retrieved_entity_ids: List[str] = field(default_factory=list)


class ConversationMemory:
    """Redis-backed 会话记忆

    Key 格式: conv:{project_id}:{session_id}
    """

    def __init__(self, redis_client: aioredis.Redis, ttl: int = 3600, max_turns: int = 20):
        self.redis = redis_client
        self.ttl = ttl
        self.max_turns = max_turns

    def _key(self, project_id: str, session_id: str) -> str:
        return f"conv:{project_id}:{session_id}"

    async def add_turn(
        self,
        project_id: str,
        session_id: str,
        turn: DialogTurn,
    ) -> None:
        """追加一轮对话并刷新 TTL"""
        key = self._key(project_id, session_id)
        data = json.dumps(asdict(turn), ensure_ascii=False)
        await self.redis.rpush(key, data)
        # 裁剪到 max_turns
        await self.redis.ltrim(key, -self.max_turns, -1)
        await self.redis.expire(key, self.ttl)
        logger.debug(f"Added turn to {key}")

    async def get_history(
        self,
        project_id: str,
        session_id: str,
        n: Optional[int] = None,
    ) -> List[DialogTurn]:
        """获取最近 n 轮对话（默认全部）"""
        key = self._key(project_id, session_id)
        start = -(n or self.max_turns)
        raw_list = await self.redis.lrange(key, start, -1)
        turns: List[DialogTurn] = []
        for raw in raw_list:
            try:
                d = json.loads(raw)
                turns.append(DialogTurn(**d))
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Skipping malformed turn: {e}")
        return turns

    async def clear(self, project_id: str, session_id: str) -> None:
        """清除会话"""
        key = self._key(project_id, session_id)
        await self.redis.delete(key)
        logger.info(f"Cleared conversation {key}")
