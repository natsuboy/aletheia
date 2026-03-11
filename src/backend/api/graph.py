"""图谱查询 API 端点"""
import asyncio
import hashlib
import json
import os
from typing import Optional, List, Dict, Any, Literal
from collections import defaultdict
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from loguru import logger
from pydantic import BaseModel, Field

from src.models.api import (
    GraphDataResponse,
    GraphNodeResponse,
    GraphEdgeResponse,
    FileContentResponse,
)
from src.graph import GraphClient
from src.graph.view_service import GraphViewService
from src.graph.snapshot_store import (
    GraphSnapshotKeys,
    async_get_json,
    async_set_json,
    default_meta,
    infer_freshness,
    now_iso,
    SNAPSHOT_VERSION,
)
from src.backend.security import CypherSanitizer

router = APIRouter(prefix="/api/graph", tags=["graph"])
VIEW_CACHE_TTL_SECONDS = 600
IMPACT_TIMEOUT_SECONDS = 25
PATH_TIMEOUT_SECONDS = 25
READMODEL_REALTIME_TIMEOUT_SECONDS = 30


class OverviewViewRequest(BaseModel):
    scope: Literal["project", "module", "file"] = "project"
    node_budget: int = Field(default=600, ge=100, le=5000)
    edge_budget: int = Field(default=1200, ge=100, le=10000)
    include_communities: bool = True
    include_processes: bool = True
    auto_budget: bool = True


class ImpactViewRequest(BaseModel):
    target_id: str = Field(..., min_length=1)
    direction: Literal["upstream", "downstream", "both"] = "both"
    max_depth: int = Field(default=3, ge=1, le=8)
    relation_types: Optional[List[str]] = None
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    include_tests: bool = False
    node_budget: int = Field(default=800, ge=100, le=5000)
    edge_budget: int = Field(default=2000, ge=100, le=15000)
    auto_budget: bool = True


class PathViewRequest(BaseModel):
    from_id: str = Field(..., min_length=1)
    to_id: str = Field(..., min_length=1)
    max_hops: int = Field(default=6, ge=1, le=12)
    relation_types: Optional[List[str]] = None
    k_paths: int = Field(default=3, ge=1, le=10)
    node_budget: int = Field(default=600, ge=100, le=5000)
    edge_budget: int = Field(default=1200, ge=100, le=10000)
    auto_budget: bool = True


class EntryFlowViewRequest(BaseModel):
    entry_id: Optional[str] = None
    max_steps: int = Field(default=12, ge=1, le=30)
    node_budget: int = Field(default=700, ge=100, le=5000)
    edge_budget: int = Field(default=1400, ge=100, le=12000)
    auto_budget: bool = True


def get_graph_client():
    """依赖注入: 获取图数据库客户端"""
    client = GraphClient()
    try:
        client.connect()
        yield client
    finally:
        client.close()


def _cache_key(project: str, task: str, payload: Dict[str, Any]) -> str:
    body = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return f"graph:view:{project}:{task}:{digest}"


def _with_metadata(
    view: Dict[str, Any],
    *,
    cache_hit: bool = False,
    partial: bool = False,
    timeout_hit: bool = False,
    coverage_mode: str = "estimated",
    freshness: str = "fresh",
    source: str = "realtime",
    snapshot_updated_at: Optional[str] = None,
    stale_reason: Optional[str] = None,
) -> Dict[str, Any]:
    out = dict(view)
    out["metadata"] = {
        "cache_hit": cache_hit,
        "partial": partial,
        "timeout_hit": timeout_hit,
        "coverage_mode": coverage_mode,
        "freshness": freshness,
        "source": source,
        "snapshot_updated_at": snapshot_updated_at,
        "snapshot_version": SNAPSHOT_VERSION,
        "stale_reason": stale_reason,
    }
    return out


def _timeout_fallback_response(task: Literal["impact", "path"], focus_ids: List[str]) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "snapshot_version": "v0",
        "task": task,
        "nodes": [],
        "edges": [],
        "focus": {
            "primary_node_ids": focus_ids,
            "suggested_actions": ["retry_with_smaller_scope", "reduce_depth_or_hops", "open_node_detail"],
        },
        "coverage": {
            "node_coverage": 0.0,
            "edge_coverage": 0.0,
            "truncated": True,
            "budgets": {"node_budget": 0, "edge_budget": 0},
            "totals": {"total_nodes": 0, "total_edges": 0, "returned_nodes": 0, "returned_edges": 0},
        },
        "explanations": ["查询超时，返回降级结果。建议缩小范围后重试。"],
        "warnings": ["本次结果为部分结果（超时降级）。"],
    }
    if task == "impact":
        base["impact"] = {
            "target_id": focus_ids[0] if focus_ids else "",
            "total_affected": 0,
            "risk": "low",
        }
    if task == "path":
        base["paths"] = []
    return base


async def _load_snapshot_meta(redis: Any, project: str) -> Dict[str, Any]:
    if redis is None:
        return default_meta()
    try:
        meta = await async_get_json(redis, GraphSnapshotKeys.meta(project))
        return meta or default_meta()
    except Exception as e:
        logger.warning(f"load snapshot meta failed: {e}")
        return default_meta()


async def _save_snapshot_meta(redis: Any, project: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    base = await _load_snapshot_meta(redis, project)
    base.update(updates)
    base["version"] = SNAPSHOT_VERSION
    base["updated_at"] = updates.get("updated_at", base.get("updated_at"))
    if redis is not None:
        try:
            await async_set_json(redis, GraphSnapshotKeys.meta(project), base)
        except Exception as e:
            logger.warning(f"save snapshot meta failed: {e}")
    return base


async def _get_active_job_state(redis: Any, project: str) -> Dict[str, Any]:
    empty = {"active": False, "status": None, "stage": None, "write_phase": None, "progress": 0}
    if redis is None:
        return empty
    try:
        job_id = await redis.get(f"project-active-job:{project}")
        if not job_id:
            return empty
        raw = await redis.get(f"job:{job_id if isinstance(job_id, str) else job_id.decode('utf-8')}")
        if not raw:
            return empty
        job = json.loads(raw if isinstance(raw, str) else raw.decode("utf-8"))
        status = str(job.get("status") or "")
        return {
            "active": status in {"pending", "running"},
            "status": status,
            "stage": job.get("stage"),
            "write_phase": job.get("write_phase"),
            "progress": int(job.get("progress", 0) or 0),
        }
    except Exception as e:
        logger.warning(f"load active job failed: {e}")
        return empty


def _build_empty_overview(project: str, body: OverviewViewRequest, reason: str) -> Dict[str, Any]:
    return {
        "snapshot_version": "v0",
        "task": "overview",
        "nodes": [],
        "edges": [],
        "focus": {
            "primary_node_ids": [],
            "suggested_actions": ["retry_after_ingestion", "reduce_node_budget", "open_status_panel"],
        },
        "coverage": {
            "node_coverage": 0.0,
            "edge_coverage": 0.0,
            "truncated": True,
            "budgets": {"node_budget": body.node_budget, "edge_budget": body.edge_budget},
            "totals": {"total_nodes": 0, "total_edges": 0, "returned_nodes": 0, "returned_edges": 0},
        },
        "explanations": [f"overview 快照暂不可用，项目 {project} 返回降级结果。"],
        "warnings": [reason],
    }


def _build_fallback_stats(project: str, reason: str) -> Dict[str, Any]:
    return {
        "project": project,
        "total_nodes": 0,
        "total_edges": 0,
        "label_distribution": {},
        "metadata": {
            "freshness": "partial",
            "source": "fallback",
            "snapshot_updated_at": None,
            "snapshot_version": SNAPSHOT_VERSION,
            "stale_reason": reason,
        },
    }


def _build_fallback_analysis_status(project: str, reason: str, progress: int = 0) -> Dict[str, Any]:
    return {
        "snapshot_version": "v0",
        "project": project,
        "stages": {
            "ingestion": "processing" if progress > 0 else "empty",
            "community": "not_ready",
            "process": "not_ready",
        },
        "progress": progress,
        "ready_features": ["overview", "impact", "path", "entry_flow"],
        "stats": {"total_nodes": 0, "communities": 0, "processes": 0},
        "metadata": {
            "freshness": "partial",
            "source": "fallback",
            "snapshot_updated_at": None,
            "snapshot_version": SNAPSHOT_VERSION,
            "stale_reason": reason,
        },
    }


def _build_project_stats_realtime(graph_client: GraphClient, project: str) -> Dict[str, Any]:
    project_id = f"project:{project}"
    project_rows = graph_client.execute_query(
        """
        MATCH (p:Project {id: $project_id})
        RETURN p
        """,
        {"project_id": project_id},
        timeout=READMODEL_REALTIME_TIMEOUT_SECONDS,
    )
    if not project_rows:
        raise HTTPException(status_code=404, detail=f"项目 {project} 不存在")

    node_rows = graph_client.execute_query(
        """
        MATCH (p:Project {id: $project_id})-[:CONTAINS|DEFINES*]->(n)
        WHERE NOT n:Project
        RETURN count(n) as total
        """,
        {"project_id": project_id},
        timeout=READMODEL_REALTIME_TIMEOUT_SECONDS,
    )
    edge_rows = graph_client.execute_query(
        """
        MATCH (p:Project {id: $project_id})-[:CONTAINS|DEFINES*]->(n)-[r]->()
        RETURN count(r) as total
        """,
        {"project_id": project_id},
        timeout=READMODEL_REALTIME_TIMEOUT_SECONDS,
    )
    label_rows = graph_client.execute_query(
        """
        MATCH (p:Project {id: $project_id})-[:CONTAINS|DEFINES*]->(n)
        WHERE NOT n:Project
        RETURN labels(n)[0] as label, count(n) as count
        ORDER BY count DESC
        """,
        {"project_id": project_id},
        timeout=READMODEL_REALTIME_TIMEOUT_SECONDS,
    )
    return {
        "project": project,
        "total_nodes": int(node_rows[0]["total"]) if node_rows else 0,
        "total_edges": int(edge_rows[0]["total"]) if edge_rows else 0,
        "label_distribution": {row["label"]: int(row["count"]) for row in label_rows},
    }


async def _refresh_read_models(redis: Any, project: str, overview_body: Dict[str, Any]) -> None:
    """异步刷新 stats/status/overview 三类快照。"""
    client = GraphClient()
    try:
        client.connect()
        service = GraphViewService(client)
        stats = _build_project_stats_realtime(client, project)
        status = service.get_analysis_status(project, fast_mode=False)
        overview = service.build_overview_view(
            project=project,
            node_budget=int(overview_body.get("node_budget", 600)),
            edge_budget=int(overview_body.get("edge_budget", 1200)),
            include_communities=bool(overview_body.get("include_communities", True)),
            include_processes=bool(overview_body.get("include_processes", True)),
            fast_mode=False,
        )
        if redis is None:
            return
        timestamp = now_iso()
        await async_set_json(redis, GraphSnapshotKeys.stats(project), stats)
        await async_set_json(redis, GraphSnapshotKeys.analysis_status(project), status)
        await async_set_json(redis, GraphSnapshotKeys.overview(project, overview_body), overview)
        await _save_snapshot_meta(
            redis,
            project,
            {
                "is_rebuilding": False,
                "last_refresh_status": "ok",
                "last_error": None,
                "updated_at": timestamp,
            },
        )
    except Exception as e:
        logger.warning(f"refresh read models failed ({project}): {e}")
        if redis is not None:
            await _save_snapshot_meta(
                redis,
                project,
                {
                    "last_refresh_status": "failed",
                    "last_error": str(e),
                    "updated_at": now_iso(),
                },
            )
    finally:
        try:
            client.close()
        except Exception:
            pass


@router.post("/{project}/view/overview")
async def get_overview_view(
    request: Request,
    project: str,
    body: OverviewViewRequest,
    force_realtime: bool = Query(default=False),
    graph_client: GraphClient = Depends(get_graph_client),
):
    """任务驱动结构总览视图。"""
    redis = getattr(request.app.state, "redis", None)
    payload = body.model_dump(exclude_none=True)
    snapshot_key = GraphSnapshotKeys.overview(project, payload)
    try:
        meta = await _load_snapshot_meta(redis, project)
        active_job = await _get_active_job_state(redis, project)
        rebuilding = bool(meta.get("is_rebuilding")) or active_job["active"]

        if not force_realtime and redis is not None:
            cached = await async_get_json(redis, snapshot_key)
            if cached:
                freshness = infer_freshness(meta, has_payload=True)
                return _with_metadata(
                    cached,
                    cache_hit=True,
                    partial=freshness in {"rebuilding", "partial"},
                    timeout_hit=False,
                    coverage_mode="estimated",
                    freshness=freshness,
                    source="snapshot",
                    snapshot_updated_at=meta.get("updated_at"),
                    stale_reason="ingesting" if rebuilding else None,
                )

        if rebuilding and not force_realtime:
            return _with_metadata(
                _build_empty_overview(project, body, "导入进行中，返回快照降级结果。"),
                cache_hit=False,
                partial=True,
                timeout_hit=False,
                coverage_mode="estimated",
                freshness="rebuilding",
                source="fallback",
                snapshot_updated_at=meta.get("updated_at"),
                stale_reason="ingesting",
            )

        service = GraphViewService(graph_client)
        logger.info(f"开始构建overview视图: project={project}, node_budget={body.node_budget}")

        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(
                service.build_overview_view,
                project,
                body.node_budget,
                body.edge_budget,
                body.include_communities,
                body.include_processes,
                True,
            )
            try:
                result = future.result(timeout=READMODEL_REALTIME_TIMEOUT_SECONDS)
                logger.info(f"overview视图构建完成")
            except concurrent.futures.TimeoutError:
                logger.warning(f"overview视图构建超时: {READMODEL_REALTIME_TIMEOUT_SECONDS}秒")
                raise asyncio.TimeoutError()
            except Exception as e:
                logger.error(f"overview视图构建失败: {e}")
                raise
        if redis is not None:
            ts = now_iso()
            await async_set_json(redis, snapshot_key, result)
            meta = await _save_snapshot_meta(
                redis,
                project,
                {
                    "updated_at": ts,
                    "is_rebuilding": False if not active_job["active"] else True,
                    "last_refresh_status": "ok",
                    "last_error": None,
                },
            )
        return _with_metadata(
            result,
            cache_hit=False,
            partial=False,
            timeout_hit=False,
            coverage_mode="estimated",
            freshness="fresh",
            source="realtime",
            snapshot_updated_at=meta.get("updated_at"),
        )
    except asyncio.TimeoutError:
        if redis is not None:
            asyncio.create_task(_refresh_read_models(redis, project, payload))
        fallback = _build_empty_overview(project, body, "overview 实时计算超时，已转为后台刷新。")
        return _with_metadata(
            fallback,
            cache_hit=False,
            partial=True,
            timeout_hit=True,
            coverage_mode="estimated",
            freshness="partial",
            source="fallback",
            stale_reason="realtime_timeout",
        )
    except Exception as e:
        logger.error(f"overview view 失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.post("/{project}/view/impact")
async def get_impact_view(
    request: Request,
    project: str,
    body: ImpactViewRequest,
    graph_client: GraphClient = Depends(get_graph_client),
):
    """任务驱动影响分析视图。"""
    try:
        redis = getattr(request.app.state, "redis", None)
        payload = body.model_dump(exclude_none=True)
        key = _cache_key(project, "impact", payload)
        if redis is not None:
            try:
                cached = await redis.get(key)
            except Exception as cache_err:
                logger.warning(f"impact cache read failed: {cache_err}")
                cached = None
            if cached:
                try:
                    data = json.loads(cached if isinstance(cached, str) else cached.decode("utf-8"))
                    return _with_metadata(data, cache_hit=True, partial=False, timeout_hit=False, coverage_mode="estimated")
                except Exception as parse_err:
                    logger.warning(f"impact cache parse failed: {parse_err}")

        service = GraphViewService(graph_client)
        result = await asyncio.wait_for(
            asyncio.to_thread(
                service.build_impact_view,
                project,
                body.target_id,
                body.direction,
                body.max_depth,
                body.relation_types,
                body.min_confidence,
                body.node_budget,
                body.edge_budget,
            ),
            timeout=IMPACT_TIMEOUT_SECONDS,
        )
        if redis is not None:
            try:
                await redis.setex(key, VIEW_CACHE_TTL_SECONDS, json.dumps(result, ensure_ascii=False))
            except Exception as cache_err:
                logger.warning(f"impact cache write failed: {cache_err}")
        return _with_metadata(result, cache_hit=False, partial=False, timeout_hit=False, coverage_mode="estimated")
    except asyncio.TimeoutError:
        fallback = _timeout_fallback_response("impact", [body.target_id])
        return _with_metadata(fallback, cache_hit=False, partial=True, timeout_hit=True, coverage_mode="estimated")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"impact view 失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.post("/{project}/view/path")
async def get_path_view(
    request: Request,
    project: str,
    body: PathViewRequest,
    graph_client: GraphClient = Depends(get_graph_client),
):
    """任务驱动路径分析视图。"""
    try:
        redis = getattr(request.app.state, "redis", None)
        payload = body.model_dump(exclude_none=True)
        key = _cache_key(project, "path", payload)
        if redis is not None:
            try:
                cached = await redis.get(key)
            except Exception as cache_err:
                logger.warning(f"path cache read failed: {cache_err}")
                cached = None
            if cached:
                try:
                    data = json.loads(cached if isinstance(cached, str) else cached.decode("utf-8"))
                    return _with_metadata(data, cache_hit=True, partial=False, timeout_hit=False, coverage_mode="estimated")
                except Exception as parse_err:
                    logger.warning(f"path cache parse failed: {parse_err}")

        service = GraphViewService(graph_client)
        result = await asyncio.wait_for(
            asyncio.to_thread(
                service.build_path_view,
                project,
                body.from_id,
                body.to_id,
                body.max_hops,
                body.relation_types,
                body.k_paths,
                body.node_budget,
                body.edge_budget,
            ),
            timeout=PATH_TIMEOUT_SECONDS,
        )
        if redis is not None:
            try:
                await redis.setex(key, VIEW_CACHE_TTL_SECONDS, json.dumps(result, ensure_ascii=False))
            except Exception as cache_err:
                logger.warning(f"path cache write failed: {cache_err}")
        return _with_metadata(result, cache_hit=False, partial=False, timeout_hit=False, coverage_mode="estimated")
    except asyncio.TimeoutError:
        fallback = _timeout_fallback_response("path", [body.from_id, body.to_id])
        return _with_metadata(fallback, cache_hit=False, partial=True, timeout_hit=True, coverage_mode="estimated")
    except Exception as e:
        logger.error(f"path view 失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.post("/{project}/view/entry-flow")
async def get_entry_flow_view(
    project: str,
    body: EntryFlowViewRequest,
    graph_client: GraphClient = Depends(get_graph_client),
):
    """任务驱动入口流程视图。"""
    try:
        service = GraphViewService(graph_client)
        result = service.build_entry_flow_view(
            project=project,
            entry_id=body.entry_id,
            max_steps=body.max_steps,
            node_budget=body.node_budget,
            edge_budget=body.edge_budget,
        )
        return _with_metadata(result, cache_hit=False, partial=False, timeout_hit=False, coverage_mode="estimated")
    except Exception as e:
        logger.error(f"entry-flow view 失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get("/{project}/analysis/status")
async def get_analysis_status(
    request: Request,
    project: str,
    force_realtime: bool = Query(default=False),
    graph_client: GraphClient = Depends(get_graph_client),
):
    """分析状态与可用特性。"""
    redis = getattr(request.app.state, "redis", None)
    try:
        meta = await _load_snapshot_meta(redis, project)
        active_job = await _get_active_job_state(redis, project)
        rebuilding = bool(meta.get("is_rebuilding")) or active_job["active"]

        if not force_realtime and redis is not None:
            cached = await async_get_json(redis, GraphSnapshotKeys.analysis_status(project))
            if cached:
                freshness = infer_freshness(meta, has_payload=True)
                cached["metadata"] = {
                    "freshness": freshness,
                    "source": "snapshot",
                    "snapshot_updated_at": meta.get("updated_at"),
                    "snapshot_version": SNAPSHOT_VERSION,
                    "stale_reason": "ingesting" if rebuilding else None,
                }
                return cached

        if rebuilding and not force_realtime:
            return _build_fallback_analysis_status(
                project,
                "ingesting",
                progress=int(active_job.get("progress") or 0),
            )

        service = GraphViewService(graph_client)
        data = await asyncio.wait_for(
            asyncio.to_thread(service.get_analysis_status, project, False),
            timeout=READMODEL_REALTIME_TIMEOUT_SECONDS,
        )
        if redis is not None:
            ts = now_iso()
            await async_set_json(redis, GraphSnapshotKeys.analysis_status(project), data)
            meta = await _save_snapshot_meta(
                redis,
                project,
                {
                    "updated_at": ts,
                    "is_rebuilding": False if not active_job["active"] else True,
                    "last_refresh_status": "ok",
                    "last_error": None,
                },
            )
        data["metadata"] = {
            "freshness": "fresh",
            "source": "realtime",
            "snapshot_updated_at": meta.get("updated_at"),
            "snapshot_version": SNAPSHOT_VERSION,
            "stale_reason": None,
        }
        return data
    except asyncio.TimeoutError:
        if redis is not None:
            asyncio.create_task(
                _refresh_read_models(
                    redis,
                    project,
                    {
                        "scope": "project",
                        "node_budget": 600,
                        "edge_budget": 1200,
                        "include_communities": True,
                        "include_processes": True,
                    },
                )
            )
        return _build_fallback_analysis_status(project, "realtime_timeout")
    except Exception as e:
        logger.error(f"analysis status 失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get("/{project}/data", response_model=GraphDataResponse)
async def get_graph_data(
    project: str,
    limit: int = Query(default=500, ge=1, le=1000, description="返回节点数量限制"),
    offset: int = Query(default=0, ge=0, description="分页偏移量"),
    node_types: Optional[str] = Query(None, description="节点类型过滤 (逗号分隔)"),
    graph_client: GraphClient = Depends(get_graph_client),
):
    """
    获取项目的图谱数据

    - **project**: 项目名称
    - **limit**: 返回节点数量限制 (1-1000)
    - **node_types**: 节点类型过滤 (可选, 例如: "Class,Function,Method")

    返回节点和边的列表
    """
    try:
        project_id = f"project:{project}"

        # 构建节点查询
        if node_types:
            # 解析并验证节点类型（防止 Cypher 注入）
            raw_types = [t.strip() for t in node_types.split(",")]
            try:
                sanitized_types = [CypherSanitizer.sanitize_identifier(t) for t in raw_types if t]
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"无效的节点类型: {str(e)}")
            labels_str = "|".join(sanitized_types)

            nodes_query = f"""
            MATCH (p:Project {{id: $project_id}})-[:CONTAINS|DEFINES*]->(n:{labels_str})
            WITH DISTINCT n SKIP $offset LIMIT $limit
            RETURN n
            """
        else:
            # 查询所有节点 (除了 Project 和 File)
            nodes_query = """
            MATCH (p:Project {id: $project_id})-[:CONTAINS|DEFINES*]->(n)
            WHERE NOT (n:Project OR n:File)
            WITH DISTINCT n SKIP $offset LIMIT $limit
            RETURN n
            """

        # 执行节点查询
        logger.info(f"查询项目 {project} 的节点 (limit={limit})")
        node_results = graph_client.execute_query(
            nodes_query,
            {"project_id": project_id, "limit": limit, "offset": offset}
        )

        # 转换节点
        nodes = []
        node_ids = []
        for record in node_results:
            node_data = record["n"]
            node_id = node_data.get("id", "")
            node_ids.append(node_id)

            # 提取标签：优先用驱动的 labels 属性，其次用 kind 属性
            label = node_data.get("kind", "Unknown")
            if hasattr(node_data, "labels"):
                labels_list = list(node_data.labels)
                if labels_list:
                    label = labels_list[0]

            # 提取属性
            properties = {k: v for k, v in node_data.items()}

            nodes.append(
                GraphNodeResponse(
                    id=node_id,
                    label=label,
                    properties=properties,
                )
            )

        logger.info(f"找到 {len(nodes)} 个节点")

        # 反向查找与这些 Symbol 关联的 File 节点，一并加入图谱
        if node_ids:
            file_query = """
            MATCH (f:File)-[:DEFINES|REFERENCES|CONTAINS]->(n)
            WHERE n.id IN $node_ids
            RETURN DISTINCT f
            """
            file_results = graph_client.execute_query(file_query, {"node_ids": node_ids})
            for record in file_results:
                fd = record["f"]
                fid = fd.get("id", "")
                if fid and fid not in node_ids:
                    node_ids.append(fid)
                    nodes.append(
                        GraphNodeResponse(
                            id=fid,
                            label="File",
                            properties={k: v for k, v in fd.items()},
                        )
                    )
            logger.info(f"加入 {len(file_results)} 个关联 File 节点，共 {len(nodes)} 个节点")

        # 查询这些节点之间的边
        if node_ids:
            edges_query = """
            MATCH (a)-[r]->(b)
            WHERE a.id IN $node_ids AND b.id IN $node_ids
            RETURN a.id as from_id, b.id as to_id, type(r) as rel_type, properties(r) as props, id(r) as edge_id
            """

            edge_results = graph_client.execute_query(
                edges_query,
                {"node_ids": node_ids}
            )

            # 转换边
            edges = []
            for record in edge_results:
                edge_id = str(record.get("edge_id", ""))
                from_id = record["from_id"]
                to_id = record["to_id"]
                rel_type = record["rel_type"]
                props = record.get("props", {}) or {}

                edges.append(
                    GraphEdgeResponse(
                        id=edge_id,
                        from_id=from_id,
                        to_id=to_id,
                        type=rel_type,
                        properties=props,
                    )
                )

            logger.info(f"找到 {len(edges)} 条边")
        else:
            edges = []

        # 统计信息（含总节点数，用于前端分页）
        count_query = """
        MATCH (p:Project {id: $project_id})-[:CONTAINS|DEFINES*]->(n)
        WHERE NOT (n:Project OR n:File)
        RETURN count(DISTINCT n) as total
        """
        count_result = graph_client.execute_query(count_query, {"project_id": project_id})
        total_nodes = count_result[0]["total"] if count_result else 0
        stats = {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "total_nodes": total_nodes,
        }

        return GraphDataResponse(
            nodes=nodes,
            edges=edges,
            stats=stats,
        )

    except Exception as e:
        logger.error(f"查询图谱数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get("/{project}/subgraph", response_model=GraphDataResponse)
async def get_subgraph(
    project: str,
    center_node: str = Query(..., description="中心节点 ID"),
    hops: int = Query(default=2, ge=1, le=5, description="跳数"),
    limit: int = Query(default=100, ge=1, le=1000, description="节点数量限制"),
    graph_client: GraphClient = Depends(get_graph_client),
):
    """获取以指定节点为中心的子图"""
    try:
        # 注意：Memgraph 不支持在变长路径中使用参数作为跳数（$hops），
        # 必须将跳数直接内联到 Cypher 字符串中。
        # 同样，$limit 在 WITH 子句中不可用，需内联。
        # project_id 过滤通过 center_id 精确定位已足够，不再额外过滤
        safe_hops = max(1, min(int(hops), 5))   # 限制范围 1-5，防注入
        safe_limit = max(1, min(int(limit), 1000))
        nodes_query = f"""
        MATCH path = (center)-[*1..{safe_hops}]-(neighbor)
        WHERE center.id = $center_id
        WITH DISTINCT neighbor
        LIMIT {safe_limit}
        RETURN neighbor AS n
        """
        node_results = graph_client.execute_query(
            nodes_query,
            {"center_id": center_node},
        )

        nodes = []
        node_ids = [center_node]
        for record in node_results:
            nd = record["n"]
            nid = nd.get("id", "")
            node_ids.append(nid)
            label = nd.get("kind", "Unknown")
            if hasattr(nd, "labels") and list(nd.labels):
                label = list(nd.labels)[0]
            nodes.append(GraphNodeResponse(id=nid, label=label, properties=dict(nd.items())))

        # 添加中心节点
        center_results = graph_client.execute_query(
            "MATCH (n) WHERE n.id = $id RETURN n", {"id": center_node}
        )
        if center_results:
            cd = center_results[0]["n"]
            cl = cd.get("kind", "Unknown")
            if hasattr(cd, "labels") and list(cd.labels):
                cl = list(cd.labels)[0]
            nodes.insert(0, GraphNodeResponse(id=center_node, label=cl, properties=dict(cd.items())))

        edges = []
        if node_ids:
            edge_results = graph_client.execute_query(
                """
                MATCH (a)-[r]->(b)
                WHERE a.id IN $ids AND b.id IN $ids
                RETURN a.id as from_id, b.id as to_id, type(r) as rel_type,
                       properties(r) as props, id(r) as edge_id
                """,
                {"ids": node_ids},
            )
            for rec in edge_results:
                edges.append(GraphEdgeResponse(
                    id=str(rec.get("edge_id", "")),
                    from_id=rec["from_id"],
                    to_id=rec["to_id"],
                    type=rec["rel_type"],
                    properties=rec.get("props") or {},
                ))

        return GraphDataResponse(
            nodes=nodes, edges=edges,
            stats={"node_count": len(nodes), "edge_count": len(edges)},
        )
    except Exception as e:
        logger.error(f"子图查询失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get("/{project}/stats")
async def get_project_stats(
    request: Request,
    project: str,
    force_realtime: bool = Query(default=False),
    graph_client: GraphClient = Depends(get_graph_client),
):
    """
    获取项目统计信息

    - **project**: 项目名称

    返回节点数量、边数量、节点类型分布等统计信息
    """
    redis = getattr(request.app.state, "redis", None)
    try:
        meta = await _load_snapshot_meta(redis, project)
        active_job = await _get_active_job_state(redis, project)
        rebuilding = bool(meta.get("is_rebuilding")) or active_job["active"]

        if not force_realtime and redis is not None:
            cached = await async_get_json(redis, GraphSnapshotKeys.stats(project))
            if cached:
                cached["metadata"] = {
                    "freshness": infer_freshness(meta, has_payload=True),
                    "source": "snapshot",
                    "snapshot_updated_at": meta.get("updated_at"),
                    "snapshot_version": SNAPSHOT_VERSION,
                    "stale_reason": "ingesting" if rebuilding else None,
                }
                return cached

        if rebuilding and not force_realtime:
            return _build_fallback_stats(project, "ingesting")

        result = await asyncio.wait_for(
            asyncio.to_thread(_build_project_stats_realtime, graph_client, project),
            timeout=READMODEL_REALTIME_TIMEOUT_SECONDS,
        )
        if redis is not None:
            ts = now_iso()
            await async_set_json(redis, GraphSnapshotKeys.stats(project), result)
            meta = await _save_snapshot_meta(
                redis,
                project,
                {
                    "updated_at": ts,
                    "is_rebuilding": False if not active_job["active"] else True,
                    "last_refresh_status": "ok",
                    "last_error": None,
                },
            )
        result["metadata"] = {
            "freshness": "fresh",
            "source": "realtime",
            "snapshot_updated_at": meta.get("updated_at"),
            "snapshot_version": SNAPSHOT_VERSION,
            "stale_reason": None,
        }
        return result
    except asyncio.TimeoutError:
        if redis is not None:
            asyncio.create_task(
                _refresh_read_models(
                    redis,
                    project,
                    {
                        "scope": "project",
                        "node_budget": 600,
                        "edge_budget": 1200,
                        "include_communities": True,
                        "include_processes": True,
                    },
                )
            )
        return _build_fallback_stats(project, "realtime_timeout")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询项目统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get("/{project}/search")
async def search_symbols(
    project: str,
    q: str = Query(..., min_length=1, description="搜索关键词"),
    type: Optional[str] = Query(None, description="节点类型过滤 (逗号分隔, 如 Function,Class)"),
    limit: int = Query(default=20, ge=1, le=100, description="结果数量限制"),
    graph_client: GraphClient = Depends(get_graph_client),
):
    """搜索符号（大小写不敏感，支持类型过滤）"""
    try:
        project_id = f"project:{project}"

        # 大小写不敏感搜索
        type_filter = ""
        if type:
            raw_types = [t.strip() for t in type.split(",") if t.strip()]
            try:
                sanitized = [CypherSanitizer.sanitize_identifier(t) for t in raw_types]
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"无效的节点类型: {str(e)}")
            type_filter = "AND labels(n)[0] IN $type_list"

        search_query = f"""
        MATCH (p:Project {{id: $project_id}})-[:CONTAINS|DEFINES*]->(n)
        WHERE toLower(n.name) CONTAINS toLower($keyword) {type_filter}
        RETURN n.id as id, n.name as name, labels(n)[0] as type,
               n.file_path as file_path, n.start_line as line_number
        ORDER BY n.name
        LIMIT $limit
        """

        params = {"project_id": project_id, "keyword": q, "limit": limit}
        if type:
            params["type_list"] = sanitized
        results = graph_client.execute_query(search_query, params)

        symbols = [
            {
                "id": record["id"],
                "name": record["name"],
                "type": record["type"],
                "file_path": record.get("file_path", ""),
                "line_number": record.get("line_number"),
            }
            for record in results
        ]

        return {
            "query": q,
            "project": project,
            "total": len(symbols),
            "symbols": symbols,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"搜索符号失败: {e}")
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")


# ── 语言检测辅助 ──
LANG_MAP = {
    ".py": "python", ".js": "javascript", ".ts": "typescript", ".tsx": "typescript",
    ".go": "go", ".java": "java", ".rs": "rust", ".rb": "ruby", ".cpp": "cpp",
    ".c": "c", ".cs": "csharp", ".php": "php", ".swift": "swift", ".kt": "kotlin",
}


def _detect_language(file_path: str) -> str:
    _, ext = os.path.splitext(file_path)
    return LANG_MAP.get(ext.lower(), "text")


def _read_code_snippet(
    file_path: str, project_root: str, start_line: int | None, end_line: int | None
) -> Dict[str, Any] | None:
    """安全读取代码片段，防止路径遍历"""
    if not file_path:
        return None

    # 拼接完整路径
    if os.path.isabs(file_path):
        full_path = file_path
    else:
        full_path = os.path.join(project_root, file_path)

    # 安全检查：realpath 防止路径遍历
    real_path = os.path.realpath(full_path)
    real_root = os.path.realpath(project_root)
    if not real_path.startswith(real_root + os.sep) and real_path != real_root:
        logger.warning(f"路径遍历尝试: {file_path} -> {real_path}")
        return None

    if not os.path.isfile(real_path):
        return None

    try:
        with open(real_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        s = max(0, (start_line or 1) - 6)
        e = min(len(lines), (end_line or (start_line or 1)) + 16)
        content = "".join(lines[s:e])

        return {
            "content": content,
            "language": _detect_language(file_path),
            "start_line": s + 1,
            "end_line": e,
            "highlight_lines": list(range(start_line or s + 1, (end_line or s + 1) + 1)),
        }
    except Exception as exc:
        logger.warning(f"读取代码片段失败: {exc}")
        return None


def _validate_project_id(project: str):
    """验证项目 ID 格式"""
    import re
    if not re.match(r'^[a-zA-Z0-9_-]{1,100}$', project):
        raise HTTPException(status_code=400, detail="无效的项目 ID 格式")
    if '..' in project or project.startswith('/'):
        raise HTTPException(status_code=400, detail="项目 ID 包含非法字符")


def _get_project_root(graph_client: GraphClient, project: str) -> str:
    """获取项目根目录路径"""
    proj_results = graph_client.execute_query(
        "MATCH (p:Project {id: $pid}) RETURN p.project_root as root",
        {"pid": f"project:{project}"},
    )
    if not proj_results:
        raise HTTPException(status_code=404, detail="项目不存在")
    root = proj_results[0]["root"]
    if not root:
        raise HTTPException(status_code=422, detail="项目未设置根目录路径")
    # 处理 file:// URI
    if root.startswith("file://"):
        root = root[7:]  # 移除 file://
    return root


def _safe_resolve_path(file_path: str, project_root: str) -> str:
    """安全解析文件路径，防止路径遍历"""
    full_path = file_path if os.path.isabs(file_path) else os.path.join(project_root, file_path)
    real_path = os.path.realpath(full_path)
    real_root = os.path.realpath(project_root)
    if not real_path.startswith(real_root + os.sep) and real_path != real_root:
        raise HTTPException(status_code=403, detail="路径不允许")
    return real_path


@router.get("/{project}/file", response_model=FileContentResponse)
async def get_file_content(
    project: str,
    path: str = Query(..., description="文件相对路径"),
    graph_client: GraphClient = Depends(get_graph_client),
):
    """读取项目中的完整文件内容"""
    _validate_project_id(project)
    project_root = _get_project_root(graph_client, project)
    logger.info(f"文件API: project_root={project_root}, path={path}")
    real_path = _safe_resolve_path(path, project_root)
    logger.info(f"文件API: real_path={real_path}, exists={os.path.isfile(real_path)}")

    if not os.path.isfile(real_path):
        raise HTTPException(
            status_code=404,
            detail=f"文件不存在: {path}。请检查项目根路径 {project_root} 是否已挂载到容器"
        )

    try:
        with open(real_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception as exc:
        logger.error(f"读取文件失败: {exc}")
        raise HTTPException(status_code=500, detail="读取文件失败")

    ext = os.path.splitext(path)[1].lstrip(".")
    language = _detect_language(path)

    return FileContentResponse(path=path, content=content, language=language)


@router.get("/{project}/node/{node_id:path}")
async def get_node_detail(
    project: str,
    node_id: str,
    graph_client: GraphClient = Depends(get_graph_client),
):
    """获取节点详情（属性 + 邻居 + 代码片段）"""
    try:
        # 查询节点属性
        node_results = graph_client.execute_query(
            "MATCH (n) WHERE n.id = $id RETURN n", {"id": node_id}
        )
        if not node_results:
            raise HTTPException(status_code=404, detail=f"节点 {node_id} 不存在")

        nd = node_results[0]["n"]
        node_label = nd.get("kind", "Unknown")
        if hasattr(nd, "labels") and list(nd.labels):
            node_label = list(nd.labels)[0]
        node_props = {k: v for k, v in nd.items()}

        # 查询出边邻居
        out_results = graph_client.execute_query(
            """MATCH (n)-[r]->(m) WHERE n.id = $id
               RETURN type(r) as rel, m.id as id, m.name as name,
                      labels(m)[0] as type""",
            {"id": node_id},
        )
        # 查询入边邻居
        in_results = graph_client.execute_query(
            """MATCH (n)<-[r]-(m) WHERE n.id = $id
               RETURN type(r) as rel, m.id as id, m.name as name,
                      labels(m)[0] as type""",
            {"id": node_id},
        )

        neighbors: Dict[str, list] = defaultdict(list)
        for rec in out_results:
            neighbors[rec["rel"]].append({
                "id": rec["id"], "name": rec.get("name", ""),
                "type": rec.get("type", ""), "direction": "outgoing",
            })
        for rec in in_results:
            neighbors[rec["rel"]].append({
                "id": rec["id"], "name": rec.get("name", ""),
                "type": rec.get("type", ""), "direction": "incoming",
            })

        # 代码片段
        file_path = nd.get("file_path", "")
        start_line = nd.get("start_line")
        end_line = nd.get("end_line")

        # 获取 project_root
        proj_results = graph_client.execute_query(
            "MATCH (p:Project {id: $pid}) RETURN p.root as root",
            {"pid": f"project:{project}"},
        )
        project_root = proj_results[0]["root"] if proj_results else None

        code_snippet = _read_code_snippet(file_path, project_root, start_line, end_line) if project_root else None

        return {
            "node": {"id": node_id, "label": node_label, "properties": node_props},
            "neighbors": dict(neighbors),
            "code_snippet": code_snippet,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取节点详情失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get("/{project}/impact/{node_id}")
async def get_impact_analysis(
    project: str,
    node_id: str,
    depth: int = Query(default=3, ge=1, le=5, description="分析深度"),
    graph_client: GraphClient = Depends(get_graph_client),
):
    """Impact Analysis：分析节点的上下游依赖"""
    try:
        # 验证节点存在
        check = graph_client.execute_query(
            "MATCH (n) WHERE n.id = $id RETURN n.id", {"id": node_id}
        )
        if not check:
            raise HTTPException(status_code=404, detail=f"节点 {node_id} 不存在")

        upstream: Dict[str, list] = defaultdict(list)
        downstream: Dict[str, list] = defaultdict(list)
        seen_up: set = set()
        seen_down: set = set()

        # 逐层查询上游（谁依赖我）— 仅代码依赖关系
        for d in range(1, depth + 1):
            results = graph_client.execute_query(
                f"""MATCH (n)<-[r:CALLS|IMPORTS|INHERITS|IMPLEMENTS|REFERENCES|OVERRIDES|TYPE_OF*{d}..{d}]-(m)
                    WHERE n.id = $id
                    RETURN DISTINCT m.id as id, m.name as name,
                           labels(m)[0] as type, type(last(r)) as rel_type""",
                {"id": node_id},
            )
            layer = []
            for rec in results:
                mid = rec["id"]
                if mid and mid not in seen_up:
                    seen_up.add(mid)
                    layer.append({
                        "id": mid, "name": rec.get("name", ""),
                        "type": rec.get("type", ""), "rel_type": rec.get("rel_type", ""),
                    })
            if layer:
                upstream[str(d)] = layer

        # 逐层查询下游（我依赖谁）— 仅代码依赖关系
        for d in range(1, depth + 1):
            results = graph_client.execute_query(
                f"""MATCH (n)-[r:CALLS|IMPORTS|INHERITS|IMPLEMENTS|REFERENCES|OVERRIDES|TYPE_OF*{d}..{d}]->(m)
                    WHERE n.id = $id
                    RETURN DISTINCT m.id as id, m.name as name,
                           labels(m)[0] as type, type(last(r)) as rel_type""",
                {"id": node_id},
            )
            layer = []
            for rec in results:
                mid = rec["id"]
                if mid and mid not in seen_down:
                    seen_down.add(mid)
                    layer.append({
                        "id": mid, "name": rec.get("name", ""),
                        "type": rec.get("type", ""), "rel_type": rec.get("rel_type", ""),
                    })
            if layer:
                downstream[str(d)] = layer

        direct = len(seen_up & seen_down) + len(upstream.get("1", [])) + len(downstream.get("1", []))
        total = len(seen_up) + len(seen_down)

        return {
            "upstream": dict(upstream),
            "downstream": dict(downstream),
            "summary": {
                "total_affected": total,
                "direct": min(direct, total),
                "indirect": max(0, total - direct),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Impact analysis 失败: {e}")
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


@router.post("/{project}/cluster")
async def cluster_project(
    project: str,
    graph_client: GraphClient = Depends(get_graph_client),
):
    """对项目执行社区聚类（Louvain 算法）"""
    try:
        from src.graph.cluster_service import ClusterService
        service = ClusterService(graph_client)
        partition = await service.cluster_project(project)
        num_communities = len(set(partition.values())) if partition else 0
        return {
            "project": project,
            "num_communities": num_communities,
            "num_nodes": len(partition),
        }
    except Exception as e:
        logger.error(f"社区聚类失败: {e}")
        raise HTTPException(status_code=500, detail=f"聚类失败: {str(e)}")


@router.post("/query")
async def graph_query(
    body: dict,
    graph_client: GraphClient = Depends(get_graph_client),
):
    """通用图查询端点（只读）"""
    cypher = body.get("cypher", "")
    params = body.get("parameters", {})
    if not cypher:
        raise HTTPException(status_code=400, detail="cypher is required")
    # 安全：禁止写操作
    upper = cypher.upper()
    for kw in ("CREATE", "MERGE", "DELETE", "SET ", "REMOVE", "DROP"):
        if kw in upper:
            raise HTTPException(status_code=400, detail=f"Write operations not allowed: {kw}")
    try:
        results = graph_client.execute_query(cypher, params)
        return {"results": results, "count": len(results)}
    except Exception as e:
        logger.error(f"图查询失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")
