"""导航 API：接口入口与引用关系查询"""
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, List, Optional, Tuple, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger

from src.graph import GraphClient
from src.models.api import (
    EntrypointReverseLookupResponse,
    GinEndpointHit,
    GinEndpointSearchResponse,
    NavReferenceEdge,
    NavReferenceNode,
    ReferenceSubgraphResponse,
)

router = APIRouter(prefix="/api/nav", tags=["navigation"])

ROUTE_CALL_RE = re.compile(
    r"""(?P<object>[A-Za-z_][\w\.]*)\.(?P<method>GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD|Any)\s*\(\s*"(?P<route>[^"]+)"\s*,\s*(?P<args>.+?)\)\s*$"""
)
GROUP_ASSIGN_RE = re.compile(
    r"""(?P<var>[A-Za-z_]\w*)\s*:=\s*(?P<parent>[A-Za-z_]\w*)\.Group\(\s*"(?P<prefix>[^"]*)"\s*\)"""
)
FUNC_DEF_RE = re.compile(r"""^\s*func\s+(?:\([^)]*\)\s*)?(?P<name>[A-Za-z_]\w*)\s*\(""")
COMMENT_RE = re.compile(r"""//.*$""")


@dataclass
class _ParsedEndpoint:
    method: str
    route: str
    handler_symbol: str
    file_path: str
    line_number: int


def get_graph_client():
    client = GraphClient()
    try:
        client.connect()
        yield client
    finally:
        client.close()


def _validate_project_id(project: str):
    if not re.match(r"^[a-zA-Z0-9_-]{1,100}$", project):
        raise HTTPException(status_code=400, detail="无效的项目 ID 格式")
    if ".." in project or project.startswith("/"):
        raise HTTPException(status_code=400, detail="项目 ID 包含非法字符")


def _get_project_root(graph_client: GraphClient, project: str) -> str:
    rows = graph_client.execute_query(
        "MATCH (p:Project {id: $pid}) RETURN p.project_root as root",
        {"pid": f"project:{project}"},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="项目不存在")
    root = rows[0].get("root")
    if not root:
        raise HTTPException(status_code=422, detail="项目未设置根目录路径")
    # 处理 file:// URI
    if root.startswith("file://"):
        root = root[7:]
    return str(root)


def _join_route(prefix: str, route: str) -> str:
    p = prefix.strip()
    r = route.strip()
    if not p:
        return r if r.startswith("/") else f"/{r}"
    if not p.startswith("/"):
        p = f"/{p}"
    if p.endswith("/"):
        p = p[:-1]
    if not r.startswith("/"):
        r = f"/{r}"
    return f"{p}{r}"


def _split_call_args(args: str) -> List[str]:
    out: List[str] = []
    buf: List[str] = []
    depth = 0
    for ch in args:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            token = "".join(buf).strip()
            if token:
                out.append(token)
            buf = []
            continue
        buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        out.append(tail)
    return out


def _normalize_handler_symbol(raw: str) -> str:
    token = raw.strip()
    if not token:
        return ""
    # 去掉函数调用后缀，例如 foo.Bar() -> foo.Bar
    if token.endswith(")"):
        token = token.split("(", 1)[0].strip()
    token = token.lstrip("&*")
    return token


def _is_go_file(path: str) -> bool:
    return path.endswith(".go") and not path.endswith("_test.go")


def _walk_go_files(root: str) -> List[str]:
    files: List[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in {"vendor", ".git", "node_modules", "dist", "build", "tmp"}]
        for name in filenames:
            full = os.path.join(dirpath, name)
            if _is_go_file(full):
                files.append(full)
    return files


def _parse_file_for_endpoints(abs_path: str, rel_path: str) -> Tuple[List[_ParsedEndpoint], Dict[str, int]]:
    endpoints: List[_ParsedEndpoint] = []
    fn_lines: Dict[str, int] = {}
    group_prefix: Dict[str, str] = {}
    group_prefix["r"] = ""
    group_prefix["router"] = ""

    try:
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            for lineno, raw in enumerate(f, start=1):
                line = COMMENT_RE.sub("", raw).strip()
                if not line:
                    continue

                fn_match = FUNC_DEF_RE.match(line)
                if fn_match:
                    fn_lines[fn_match.group("name")] = lineno

                group_match = GROUP_ASSIGN_RE.search(line)
                if group_match:
                    var = group_match.group("var")
                    parent = group_match.group("parent")
                    prefix = group_match.group("prefix")
                    parent_prefix = group_prefix.get(parent, "")
                    group_prefix[var] = _join_route(parent_prefix, prefix)

                route_match = ROUTE_CALL_RE.search(line)
                if not route_match:
                    continue

                obj = route_match.group("object").split(".")[0]
                method = route_match.group("method").upper()
                route = route_match.group("route")
                args = _split_call_args(route_match.group("args"))
                if not args:
                    continue
                handler = _normalize_handler_symbol(args[-1])
                if not handler:
                    continue

                route_prefix = group_prefix.get(obj, "")
                full_route = _join_route(route_prefix, route)
                endpoints.append(
                    _ParsedEndpoint(
                        method="ANY" if method == "ANY" else method,
                        route=full_route,
                        handler_symbol=handler,
                        file_path=rel_path,
                        line_number=lineno,
                    )
                )
    except Exception as exc:
        logger.warning(f"解析 Go 文件失败: {abs_path} ({exc})")
    return endpoints, fn_lines


def _index_project_endpoints(project_root: str) -> Tuple[List[_ParsedEndpoint], Dict[str, Dict[str, int]]]:
    all_eps: List[_ParsedEndpoint] = []
    function_lines_by_file: Dict[str, Dict[str, int]] = {}
    for abs_path in _walk_go_files(project_root):
        rel = os.path.relpath(abs_path, project_root).replace("\\", "/")
        eps, fn_lines = _parse_file_for_endpoints(abs_path, rel)
        if eps:
            all_eps.extend(eps)
        if fn_lines:
            function_lines_by_file[rel] = fn_lines
    return all_eps, function_lines_by_file


def _fetch_function_nodes_by_file(
    graph_client: GraphClient,
    file_path: str,
) -> Dict[str, Dict[str, Any]]:
    rows = graph_client.execute_query(
        """
        MATCH (n)
        WHERE labels(n)[0] IN ['Function', 'Method']
          AND (n.file_path = $file OR n.file_path ENDS WITH $file)
        RETURN n.id AS id, n.name AS name, labels(n)[0] AS label, n.start_line AS start_line
        """,
        {"file": file_path},
    )
    out: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        out[name] = {
            "id": row.get("id"),
            "label": row.get("label"),
            "start_line": row.get("start_line"),
        }
    return out


def _score_endpoint_hit(ep: _ParsedEndpoint, query: str, mapped: bool) -> float:
    if not query:
        return 0.5 + (0.3 if mapped else 0.0)
    q = query.lower()
    text = f"{ep.method} {ep.route} {ep.handler_symbol} {ep.file_path}".lower()
    score = 0.0
    if ep.route.lower().startswith(q):
        score += 0.7
    if q in ep.route.lower():
        score += 0.4
    if q in ep.handler_symbol.lower():
        score += 0.35
    if q in ep.file_path.lower():
        score += 0.2
    if q in text:
        score += 0.1
    if mapped:
        score += 0.2
    return min(score, 1.0)


@lru_cache(maxsize=16)
def _cached_scan(project_root: str) -> Tuple[List[_ParsedEndpoint], Dict[str, Dict[str, int]]]:
    return _index_project_endpoints(project_root)


def _get_gin_endpoint_hits(
    graph_client: GraphClient,
    project: str,
    query: str,
    limit: int,
) -> List[GinEndpointHit]:
    project_root = _get_project_root(graph_client, project)
    parsed_endpoints, _ = _cached_scan(project_root)

    function_node_cache: Dict[str, Dict[str, Dict[str, Any]]] = {}
    hits: List[GinEndpointHit] = []
    query_norm = query.strip().lower()

    for ep in parsed_endpoints:
        handler_leaf = ep.handler_symbol.split(".")[-1]
        if ep.file_path not in function_node_cache:
            function_node_cache[ep.file_path] = _fetch_function_nodes_by_file(graph_client, ep.file_path)
        fn_map = function_node_cache[ep.file_path]
        node_info = fn_map.get(handler_leaf)

        # 过滤（若 query 不为空）
        if query_norm:
            search_text = f"{ep.method} {ep.route} {ep.handler_symbol} {ep.file_path}".lower()
            if query_norm not in search_text:
                continue

        score = _score_endpoint_hit(ep, query_norm, mapped=node_info is not None)
        hits.append(
            GinEndpointHit(
                method=ep.method,
                route=ep.route,
                handler_symbol=ep.handler_symbol,
                file_path=ep.file_path,
                start_line=(int(node_info["start_line"]) if node_info and node_info.get("start_line") else None)
                or ep.line_number,
                node_id=(str(node_info["id"]) if node_info and node_info.get("id") else None),
                score=round(score, 4),
            )
        )

    hits.sort(key=lambda x: x.score, reverse=True)
    return hits[:limit]


def _resolve_symbol_node_id(graph_client: GraphClient, project: str, symbol: str) -> str:
    symbol = symbol.strip()
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol 不能为空")

    exists = graph_client.execute_query("MATCH (n) WHERE n.id = $id RETURN n.id as id LIMIT 1", {"id": symbol})
    if exists:
        return symbol

    rows = graph_client.execute_query(
        """
        MATCH (p:Project {id: $pid})-[:CONTAINS|DEFINES*]->(n)
        WHERE toLower(n.name) CONTAINS toLower($keyword)
        RETURN n.id AS id, n.name AS name
        ORDER BY n.name
        LIMIT 10
        """,
        {"pid": f"project:{project}", "keyword": symbol},
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"未找到符号: {symbol}")

    for row in rows:
        if str(row.get("name", "")).lower() == symbol.lower():
            return str(row["id"])
    return str(rows[0]["id"])


def _fetch_node_meta(graph_client: GraphClient, node_ids: List[str]) -> Dict[str, NavReferenceNode]:
    if not node_ids:
        return {}
    rows = graph_client.execute_query(
        """
        MATCH (n)
        WHERE n.id IN $ids
        RETURN n.id AS id, coalesce(n.name, '') AS name, labels(n)[0] AS label,
               n.file_path AS file_path, n.start_line AS start_line, n.end_line AS end_line
        """,
        {"ids": node_ids},
    )
    out: Dict[str, NavReferenceNode] = {}
    for row in rows:
        nid = str(row["id"])
        out[nid] = NavReferenceNode(
            id=nid,
            name=str(row.get("name") or ""),
            label=str(row.get("label") or "Unknown"),
            file_path=str(row.get("file_path")) if row.get("file_path") else None,
            start_line=int(row.get("start_line")) if row.get("start_line") is not None else None,
            end_line=int(row.get("end_line")) if row.get("end_line") is not None else None,
        )
    return out


@router.get("/{project}/gin/endpoints", response_model=GinEndpointSearchResponse)
async def search_gin_endpoints(
    project: str,
    q: str = Query(default="", description="接口关键词"),
    limit: int = Query(default=30, ge=1, le=200),
    graph_client: GraphClient = Depends(get_graph_client),
):
    _validate_project_id(project)
    hits = _get_gin_endpoint_hits(graph_client, project, q, limit)
    return GinEndpointSearchResponse(project=project, query=q, total=len(hits), hits=hits)


@router.get("/{project}/references", response_model=ReferenceSubgraphResponse)
async def get_references_subgraph(
    project: str,
    symbol: str = Query(..., description="节点 ID 或符号名"),
    direction: str = Query(default="both", pattern="^(in|out|both)$"),
    depth: int = Query(default=2, ge=1, le=4),
    limit: int = Query(default=300, ge=20, le=2000),
    graph_client: GraphClient = Depends(get_graph_client),
):
    _validate_project_id(project)
    center_id = _resolve_symbol_node_id(graph_client, project, symbol)

    visited_nodes = {center_id}
    edges: Dict[Tuple[str, str, str, str], NavReferenceEdge] = {}
    frontier = {center_id}
    truncated = False
    max_edges = limit

    for _hop in range(depth):
        if not frontier:
            break
        next_frontier = set()

        if direction in {"out", "both"}:
            rows = graph_client.execute_query(
                """
                MATCH (p:Project {id: $pid})
                MATCH (p)-[:CONTAINS|DEFINES*]->(a)-[r]->(b)
                WHERE a.id IN $ids
                  AND EXISTS { MATCH (p)-[:CONTAINS|DEFINES*]->(b) }
                RETURN a.id AS source_id, b.id AS target_id, type(r) AS rel_type
                LIMIT $edge_cap
                """,
                {"pid": f"project:{project}", "ids": list(frontier), "edge_cap": max_edges},
            )
            for row in rows:
                edge = NavReferenceEdge(
                    source_id=str(row["source_id"]),
                    target_id=str(row["target_id"]),
                    rel_type=str(row["rel_type"]),
                    direction="outgoing",
                )
                key = (edge.source_id, edge.target_id, edge.rel_type, edge.direction)
                edges[key] = edge
                next_frontier.add(edge.target_id)
                visited_nodes.add(edge.target_id)
                visited_nodes.add(edge.source_id)
                if len(edges) >= max_edges:
                    truncated = True
                    break
            if truncated:
                break

        if direction in {"in", "both"}:
            rows = graph_client.execute_query(
                """
                MATCH (p:Project {id: $pid})
                MATCH (a)-[r]->(b)<-[:CONTAINS|DEFINES*]-(p)
                WHERE b.id IN $ids
                  AND EXISTS { MATCH (p)-[:CONTAINS|DEFINES*]->(a) }
                RETURN a.id AS source_id, b.id AS target_id, type(r) AS rel_type
                LIMIT $edge_cap
                """,
                {"pid": f"project:{project}", "ids": list(frontier), "edge_cap": max_edges},
            )
            for row in rows:
                edge = NavReferenceEdge(
                    source_id=str(row["source_id"]),
                    target_id=str(row["target_id"]),
                    rel_type=str(row["rel_type"]),
                    direction="incoming",
                )
                key = (edge.source_id, edge.target_id, edge.rel_type, edge.direction)
                edges[key] = edge
                next_frontier.add(edge.source_id)
                visited_nodes.add(edge.target_id)
                visited_nodes.add(edge.source_id)
                if len(edges) >= max_edges:
                    truncated = True
                    break
            if truncated:
                break

        frontier = next_frontier - {center_id}

    node_meta = _fetch_node_meta(graph_client, list(visited_nodes))
    return ReferenceSubgraphResponse(
        project=project,
        symbol=symbol,
        center_node_id=center_id,
        depth=depth,
        direction=direction,  # type: ignore[arg-type]
        truncated=truncated,
        stats={"node_count": len(node_meta), "edge_count": len(edges), "depth": depth},
        nodes=list(node_meta.values()),
        edges=list(edges.values()),
    )


@router.get("/{project}/entrypoint/{node_id:path}", response_model=EntrypointReverseLookupResponse)
async def reverse_lookup_entrypoint(
    project: str,
    node_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    graph_client: GraphClient = Depends(get_graph_client),
):
    _validate_project_id(project)
    hits = _get_gin_endpoint_hits(graph_client, project, query="", limit=500)
    matched = [h for h in hits if h.node_id == node_id][:limit]
    return EntrypointReverseLookupResponse(project=project, node_id=node_id, hits=matched)
