import hashlib
import json
import redis
from typing import Optional, List, Dict, Any
from src.backend.config import get_settings


class QueryCache:
    def __init__(self):
        settings = get_settings()
        self.redis = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            decode_responses=True,
        )

    def _key(self, query: str, project_id: str, k: int) -> str:
        raw = f"{query}:{project_id}:{k}"
        return f"cache:query:{hashlib.md5(raw.encode()).hexdigest()}"

    def get(self, query: str, project_id: str, k: int) -> Optional[List[Dict[str, Any]]]:
        data = self.redis.get(self._key(query, project_id, k))
        if data:
            return json.loads(data)
        return None

    def set(self, query: str, project_id: str, k: int, result: List[Dict[str, Any]], ttl: int = 300):
        self.redis.setex(self._key(query, project_id, k), ttl, json.dumps(result))
