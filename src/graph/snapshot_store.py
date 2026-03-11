"""图谱快照读模型存储工具（Redis）。"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional


SNAPSHOT_VERSION = "v1"
SNAPSHOT_TTL_SECONDS = 86400


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class GraphSnapshotKeys:
    """图谱快照 Redis key 规范。"""

    @staticmethod
    def stats(project: str) -> str:
        return f"graph:snapshot:{project}:stats:{SNAPSHOT_VERSION}"

    @staticmethod
    def analysis_status(project: str) -> str:
        return f"graph:snapshot:{project}:analysis_status:{SNAPSHOT_VERSION}"

    @staticmethod
    def overview(project: str, payload: Dict[str, Any]) -> str:
        body = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
        return f"graph:snapshot:{project}:overview:{digest}:{SNAPSHOT_VERSION}"

    @staticmethod
    def meta(project: str) -> str:
        return f"graph:snapshot_meta:{project}:{SNAPSHOT_VERSION}"


def default_meta() -> Dict[str, Any]:
    return {
        "version": SNAPSHOT_VERSION,
        "updated_at": None,
        "is_rebuilding": False,
        "last_refresh_status": "unknown",
        "last_error": None,
    }


def infer_freshness(meta: Optional[Dict[str, Any]], has_payload: bool) -> str:
    """根据 meta 与 payload 是否存在推断 freshness。"""
    if meta and meta.get("is_rebuilding"):
        return "rebuilding" if has_payload else "partial"
    if has_payload:
        return "fresh"
    if meta and meta.get("last_refresh_status") == "failed":
        return "stale"
    return "partial"


def sync_get_json(redis_client: Any, key: str) -> Optional[Dict[str, Any]]:
    raw = redis_client.get(key)
    if not raw:
        return None
    return json.loads(raw if isinstance(raw, str) else raw.decode("utf-8"))


def sync_set_json(redis_client: Any, key: str, value: Dict[str, Any], ttl: int = SNAPSHOT_TTL_SECONDS) -> None:
    redis_client.setex(key, ttl, json.dumps(value, ensure_ascii=False))


async def async_get_json(redis_client: Any, key: str) -> Optional[Dict[str, Any]]:
    raw = await redis_client.get(key)
    if not raw:
        return None
    return json.loads(raw if isinstance(raw, str) else raw.decode("utf-8"))


async def async_set_json(redis_client: Any, key: str, value: Dict[str, Any], ttl: int = SNAPSHOT_TTL_SECONDS) -> None:
    await redis_client.setex(key, ttl, json.dumps(value, ensure_ascii=False))
