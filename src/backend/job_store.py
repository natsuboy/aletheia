import json
import redis
from typing import Dict, Any, Optional
from uuid import uuid4
from src.backend.config import get_settings


class RedisJobStore:
    def __init__(self):
        settings = get_settings()
        self.redis = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            decode_responses=True,
        )
        self.ttl = 86400  # 24 hours

    def _key(self, job_id: str) -> str:
        return f"job:{job_id}"

    def _with_defaults(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """补齐任务观测字段默认值，保证跨模块一致。"""
        normalized = dict(data)
        normalized.setdefault("trace_id", str(uuid4()))
        normalized.setdefault("retry_count", 0)
        normalized.setdefault("failure_class", None)
        return normalized

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        data = self.redis.get(self._key(job_id))
        if data:
            result = json.loads(data)
            result.setdefault("updated_at", result.get("created_at"))
            return self._with_defaults(result)
        return None

    def set(self, job_id: str, data: Dict[str, Any]):
        normalized = self._with_defaults(data)
        self.redis.setex(self._key(job_id), self.ttl, json.dumps(normalized))

    def update(self, job_id: str, updates: Dict[str, Any]):
        from datetime import datetime
        updates.setdefault("updated_at", datetime.utcnow().isoformat())
        updates = self._with_defaults(updates)
        current = self.get(job_id)
        if current:
            current.update(updates)
            self.set(job_id, current)
        else:
            self.set(job_id, updates)

    def set_project_wiki_job(self, project_id: str, job_id: str):
        """project_id -> 活跃 wiki job_id 映射"""
        self.redis.setex(f"wiki-active:{project_id}", self.ttl, job_id)

    def get_project_wiki_job(self, project_id: str) -> Optional[str]:
        """查询项目活跃的 wiki job_id"""
        return self.redis.get(f"wiki-active:{project_id}")

    def clear_project_wiki_job(self, project_id: str):
        """清除映射"""
        self.redis.delete(f"wiki-active:{project_id}")

    def set_project_active_job(self, project_name: str, job_id: str):
        """project_name -> 活跃 ingestion job_id 映射"""
        self.redis.setex(f"project-active-job:{project_name}", self.ttl, job_id)

    def get_project_active_job(self, project_name: str) -> Optional[str]:
        """查询项目当前活跃的 ingestion job_id"""
        return self.redis.get(f"project-active-job:{project_name}")

    def clear_project_active_job(self, project_name: str):
        """清除项目活跃 ingestion 任务映射。"""
        self.redis.delete(f"project-active-job:{project_name}")


job_store = RedisJobStore()
