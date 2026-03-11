"""任务驱动图视图服务。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List

from src.graph import GraphClient


@dataclass
class Budget:
    node_budget: int
    edge_budget: int


class GraphViewService:
    """根据分析任务构建可消费子图视图。"""

    def __init__(self, graph_client: GraphClient):
        self.graph_client = graph_client

    @staticmethod
    def _project_id(project: str) -> str:
        return project if project.startswith("project:") else f"project:{project}"

    @staticmethod
    def calculate_adaptive_budget(total_nodes: int, total_edges: int, task: str) -> Budget:
        """根据图规模计算自适应预算"""
        base = {"overview": (600, 1200), "impact": (800, 2000), "path": (600, 1200), "entry_flow": (700, 1400)}
        base_nodes, base_edges = base.get(task, (600, 1200))
        scale = 0.5 if total_nodes < 500 else 1.0 if total_nodes < 2000 else 1.5 if total_nodes < 10000 else 2.5
        edge_mult = 1.5 if total_edges / max(total_nodes, 1) > 5 else 1.2 if total_edges / max(total_nodes, 1) > 3 else 1.0
        return Budget(min(int(base_nodes * scale), 5000), min(int(base_edges * scale * edge_mult), 15000))

    def _get_graph_stats(self, project_id: str) -> Dict[str, int]:
        """快速获取图统计"""
        node_rows = self.graph_client.execute_query(
            "MATCH (p:Project {id: $pid})-[:CONTAINS|DEFINES*]->(n) WHERE NOT n:Project RETURN count(DISTINCT n) AS total",
            {"pid": project_id}
        )
        edge_rows = self.graph_client.execute_query(
            "MATCH (p:Project {id: $pid})-[:CONTAINS|DEFINES*]->(n1), (p)-[:CONTAINS|DEFINES*]->(n2), (n1)-[r]->(n2) RETURN count(DISTINCT r) AS total",
            {"pid": project_id}
        )
        return {"total_nodes": int(node_rows[0]["total"]) if node_rows else 0, "total_edges": int(edge_rows[0]["total"]) if edge_rows else 0}

    @staticmethod
    def _node_label(node_data: Any) -> str:
        label = node_data.get("kind", "Unknown")
        if hasattr(node_data, "labels"):
            labels = list(node_data.labels)
            if labels:
                label = labels[0]
        return label

    def _node_to_dto(self, node_data: Any) -> Dict[str, Any]:
        props = dict(node_data.items())
        return {
            "id": str(props.get("id", "")),
            "label": self._node_label(node_data),
            "name": str(props.get("name") or props.get("id") or ""),
            "project_id": str(props.get("project_id") or ""),
            "file_path": str(props.get("file_path") or props.get("path") or ""),
            "start_line": int(props["start_line"]) if props.get("start_line") is not None else None,
            "end_line": int(props["end_line"]) if props.get("end_line") is not None else None,
            "language": str(props.get("language") or ""),
            "kind": str(props.get("kind") or ""),
            "properties": props,
        }

    @staticmethod
    def _edge_to_dto(rec: Dict[str, Any]) -> Dict[str, Any]:
        props = rec.get("props") or {}
        return {
            "id": str(rec.get("edge_id", "")),
            "source_id": str(rec.get("from_id", "")),
            "target_id": str(rec.get("to_id", "")),
            "type": str(rec.get("rel_type", "")),
            "confidence": float(props.get("confidence", 1.0)),
            "evidence_count": int(props.get("count", 1)) if isinstance(props, dict) else 1,
            "provenance": str(props.get("reason", "derived")) if isinstance(props, dict) else "derived",
            "properties": props,
        }

    def _query_edges_between(self, node_ids: Iterable[str], edge_budget: int) -> List[Dict[str, Any]]:
        ids = [nid for nid in node_ids if nid]
        if not ids:
            return []
        rows = self.graph_client.execute_query(
            """
            MATCH (a)-[r]->(b)
            WHERE a.id IN $ids AND b.id IN $ids
            RETURN a.id AS from_id, b.id AS to_id, type(r) AS rel_type,
                   properties(r) AS props, id(r) AS edge_id
            LIMIT $edge_budget
            """,
            {"ids": ids, "edge_budget": edge_budget},
        )
        return [self._edge_to_dto(r) for r in rows]

    def _estimate_coverage(
        self,
        project_id: str,
        node_count: int,
        edge_count: int,
        budget: Budget,
        fast_mode: bool = True,
    ) -> Dict[str, Any]:
        total_nodes = 0
        total_edges = 0
        try:
            node_rows = self.graph_client.execute_query(
                """
                MATCH (p:Project)
                WHERE p.id = $project_id
                MATCH (p)-[:CONTAINS|DEFINES*]->(n)
                WHERE NOT (n:Project)
                RETURN count(DISTINCT n) AS total
                """,
                {"project_id": project_id},
            )
            total_nodes = int(node_rows[0].get("total", 0)) if node_rows else 0
        except Exception:
            total_nodes = 0

        try:
            if fast_mode:
                total_edges = max(edge_count, budget.edge_budget)
            else:
                edge_rows = self.graph_client.execute_query(
                    """
                    MATCH (p:Project)
                    WHERE p.id = $project_id
                    MATCH (p)-[:CONTAINS|DEFINES*]->(n1)
                    MATCH (p)-[:CONTAINS|DEFINES*]->(n2)
                    MATCH (n1)-[r]->(n2)
                    RETURN count(DISTINCT r) AS total
                    """,
                    {"project_id": project_id},
                )
                total_edges = int(edge_rows[0].get("total", 0)) if edge_rows else 0
        except Exception:
            total_edges = 0

        node_coverage = (node_count / total_nodes) if total_nodes > 0 else 1.0
        edge_coverage = (edge_count / total_edges) if total_edges > 0 else 1.0
        truncated = node_count >= budget.node_budget or edge_count >= budget.edge_budget

        return {
            "node_coverage": round(min(node_coverage, 1.0), 4),
            "edge_coverage": round(min(edge_coverage, 1.0), 4),
            "truncated": truncated,
            "budgets": {
                "node_budget": budget.node_budget,
                "edge_budget": budget.edge_budget,
            },
            "totals": {
                "total_nodes": total_nodes,
                "total_edges": total_edges,
                "returned_nodes": node_count,
                "returned_edges": edge_count,
            },
        }

    def _build_view_response(
        self,
        project_id: str,
        task: str,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        budget: Budget,
        focus_ids: List[str],
        explanations: List[str],
        warnings: List[str],
        fast_mode: bool = True,
    ) -> Dict[str, Any]:
        return {
            "snapshot_version": "v0",
            "task": task,
            "nodes": nodes,
            "edges": edges,
            "focus": {
                "primary_node_ids": focus_ids,
                "suggested_actions": [
                    "run_impact",
                    "run_path",
                    "open_node_detail",
                ],
            },
            "coverage": self._estimate_coverage(project_id, len(nodes), len(edges), budget, fast_mode=fast_mode),
            "explanations": explanations,
            "warnings": warnings,
        }

    def _direct_impact_counts(self, target_id: str, rel_types: List[str]) -> Dict[str, int]:
        # Memgraph 不支持双 WHERE 也不支持 type(r) IN $list，内联关系类型到模式
        rel_str = "|".join(rel_types)
        upstream_rows = self.graph_client.execute_query(
            f"""
            MATCH (n)<-[:{rel_str}]-(m)
            WHERE n.id = $target_id
            RETURN count(DISTINCT m) AS total
            """,
            {"target_id": target_id},
        )
        downstream_rows = self.graph_client.execute_query(
            f"""
            MATCH (n)-[:{rel_str}]->(m)
            WHERE n.id = $target_id
            RETURN count(DISTINCT m) AS total
            """,
            {"target_id": target_id},
        )
        upstream = int(upstream_rows[0].get("total", 0)) if upstream_rows else 0
        downstream = int(downstream_rows[0].get("total", 0)) if downstream_rows else 0
        return {"upstream": upstream, "downstream": downstream, "total": upstream + downstream}

    def build_overview_view(
        self,
        project: str,
        node_budget: int | None = None,
        edge_budget: int | None = None,
        include_communities: bool = True,
        include_processes: bool = True,
        fast_mode: bool = True,
        auto_budget: bool = True,
    ) -> Dict[str, Any]:
        project_id = self._project_id(project)

        if auto_budget and (node_budget is None or edge_budget is None):
            stats = self._get_graph_stats(project_id)
            budget = self.calculate_adaptive_budget(stats["total_nodes"], stats["total_edges"], "overview")
            node_budget, edge_budget = budget.node_budget, budget.edge_budget
        else:
            node_budget = node_budget or 600
            edge_budget = edge_budget or 1200

        budget = Budget(node_budget=node_budget, edge_budget=edge_budget)

        node_rows = self.graph_client.execute_query(
            """
            MATCH (p:Project)
            WHERE p.id = $project_id
            MATCH (p)-[:CONTAINS|DEFINES*]->(n)
            WHERE NOT (n:Project)
            WITH DISTINCT n
            RETURN n
            LIMIT $node_budget
            """,
            {"project_id": project_id, "node_budget": node_budget},
        )
        nodes = [self._node_to_dto(row["n"]) for row in node_rows]
        node_ids = [n["id"] for n in nodes]
        edges = self._query_edges_between(node_ids, edge_budget)

        if not include_communities:
            nodes = [n for n in nodes if n["label"] != "Community"]
            keep = {n["id"] for n in nodes}
            edges = [e for e in edges if e["source_id"] in keep and e["target_id"] in keep]
        if not include_processes:
            nodes = [n for n in nodes if n["label"] != "Process"]
            keep = {n["id"] for n in nodes}
            edges = [e for e in edges if e["source_id"] in keep and e["target_id"] in keep]
        focus_ids = [n["id"] for n in nodes[:3]]

        return self._build_view_response(
            project_id=project_id,
            task="overview",
            nodes=nodes,
            edges=edges,
            budget=budget,
            focus_ids=focus_ids,
            explanations=["结构总览基于项目内可达节点构建。"],
            warnings=[] if nodes else ["当前项目暂无可展示节点。"],
            fast_mode=fast_mode,
        )

    def build_impact_view(
        self,
        project: str,
        target_id: str,
        direction: str = "both",
        max_depth: int = 3,
        relation_types: List[str] | None = None,
        min_confidence: float = 0.0,
        node_budget: int | None = None,
        edge_budget: int | None = None,
        auto_budget: bool = True,
    ) -> Dict[str, Any]:
        project_id = self._project_id(project)

        if auto_budget and (node_budget is None or edge_budget is None):
            stats = self._get_graph_stats(project_id)
            budget = self.calculate_adaptive_budget(stats["total_nodes"], stats["total_edges"], "impact")
            node_budget, edge_budget = budget.node_budget, budget.edge_budget
        else:
            node_budget = node_budget or 800
            edge_budget = edge_budget or 2000

        budget = Budget(node_budget=node_budget, edge_budget=edge_budget)
        rel_types = relation_types or ["CALLS", "IMPORTS", "INHERITS", "IMPLEMENTS", "REFERENCES", "OVERRIDES", "TYPE_OF"]

        target_rows = self.graph_client.execute_query("MATCH (n) WHERE n.id = $id RETURN n", {"id": target_id})
        if not target_rows:
            raise ValueError(f"target node not found: {target_id}")

        nodes: Dict[str, Dict[str, Any]] = {target_id: self._node_to_dto(target_rows[0]["n"])}
        edges: List[Dict[str, Any]] = []

        def collect_paths(incoming: bool):
            # Memgraph 不支持参数化路径长度和 all() 谓词里的 WHERE
            # 把 max_depth 和关系类型直接内联到查询字符串中
            rel_str = "|".join(rel_types)
            depth = int(max_depth)
            arrow = f"<-[:{rel_str}*1..{depth}]-" if incoming else f"-[:{rel_str}*1..{depth}]->"
            rows = self.graph_client.execute_query(
                f"""
                MATCH (root)
                WHERE root.id = $target_id
                MATCH p = (root){arrow}(n)
                UNWIND nodes(p) AS nd
                WITH DISTINCT nd
                RETURN nd AS n
                LIMIT $node_budget
                """,
                {
                    "target_id": target_id,
                    "node_budget": node_budget,
                },
            )
            for row in rows:
                dto = self._node_to_dto(row["n"])
                nodes[dto["id"]] = dto

        if direction in ("both", "upstream"):
            collect_paths(incoming=True)
        if direction in ("both", "downstream"):
            collect_paths(incoming=False)

        edge_rows = self._query_edges_between(nodes.keys(), edge_budget)
        if min_confidence > 0:
            edge_rows = [e for e in edge_rows if e.get("confidence", 1.0) >= min_confidence]

        for e in edge_rows:
            if e["type"] in rel_types:
                edges.append(e)

        impacted = len(nodes) - 1
        direct_counts = self._direct_impact_counts(target_id, rel_types)
        direct = direct_counts["total"]
        avg_conf = (sum(e.get("confidence", 1.0) for e in edges) / len(edges)) if edges else 0.0
        risk_score = impacted * 0.45 + direct * 1.2 + avg_conf * 20.0
        risk = "low"
        if risk_score >= 120:
            risk = "critical"
        elif risk_score >= 70:
            risk = "high"
        elif risk_score >= 30:
            risk = "medium"

        resp = self._build_view_response(
            project_id=project_id,
            task="impact",
            nodes=list(nodes.values()),
            edges=edges,
            budget=budget,
            focus_ids=[target_id],
            explanations=[f"影响分析方向: {direction}, 深度: {max_depth}。"],
            warnings=[] if impacted > 0 else ["未找到显著影响节点，可能关系稀疏或超出深度阈值。"],
            fast_mode=True,
        )
        resp["impact"] = {
            "target_id": target_id,
            "total_affected": impacted,
            "direct_affected": direct,
            "upstream_direct": direct_counts["upstream"],
            "downstream_direct": direct_counts["downstream"],
            "avg_confidence": round(avg_conf, 4),
            "risk_score": round(risk_score, 2),
            "risk": risk,
        }
        return resp

    def build_path_view(
        self,
        project: str,
        from_id: str,
        to_id: str,
        max_hops: int = 6,
        relation_types: List[str] | None = None,
        k_paths: int = 3,
        node_budget: int | None = None,
        edge_budget: int | None = None,
        auto_budget: bool = True,
    ) -> Dict[str, Any]:
        project_id = self._project_id(project)

        if auto_budget and (node_budget is None or edge_budget is None):
            stats = self._get_graph_stats(project_id)
            budget = self.calculate_adaptive_budget(stats["total_nodes"], stats["total_edges"], "path")
            node_budget, edge_budget = budget.node_budget, budget.edge_budget
        else:
            node_budget = node_budget or 600
            edge_budget = edge_budget or 1200

        budget = Budget(node_budget=node_budget, edge_budget=edge_budget)
        rel_types = relation_types or ["CALLS", "IMPORTS", "INHERITS", "IMPLEMENTS", "REFERENCES", "OVERRIDES", "TYPE_OF"]

        # Memgraph 不支持参数化路径长度和 all() 谓词 WHERE，内联 max_hops 和关系类型
        rel_str = "|".join(rel_types)
        hops = int(max_hops)
        path_scan_limit = max(k_paths * 4, 12)
        rows = self.graph_client.execute_query(
            f"""
            MATCH (src), (dst)
            WHERE src.id = $from_id AND dst.id = $to_id
            MATCH p = (src)-[:{rel_str}*1..{hops}]->(dst)
            RETURN p
            LIMIT {path_scan_limit}
            """,
            {
                "from_id": from_id,
                "to_id": to_id,
            },
        )

        node_ids: List[str] = []
        ranked_paths: List[Dict[str, Any]] = []

        for row in rows:
            path = row.get("p")
            if not path:
                continue
            p_nodes = [self._node_to_dto(n) for n in path.nodes]
            ids = [n["id"] for n in p_nodes if n.get("id")]
            node_ids.extend(ids)

            rel_confidences: List[float] = []
            for rel in path.relationships:
                try:
                    rel_props = dict(rel.items())
                except Exception:
                    rel_props = {}
                rel_confidences.append(float(rel_props.get("confidence", 1.0)))

            length = max(0, len(ids) - 1)
            avg_confidence = (sum(rel_confidences) / len(rel_confidences)) if rel_confidences else 1.0
            score = (avg_confidence * 100.0) - (length * 4.0)
            ranked_paths.append(
                {
                    "length": length,
                    "node_ids": ids,
                    "avg_confidence": round(avg_confidence, 4),
                    "score": round(score, 2),
                }
            )

        ranked_paths.sort(key=lambda p: (-p["score"], p["length"]))
        path_summaries: List[Dict[str, Any]] = []
        for idx, p in enumerate(ranked_paths[:k_paths], start=1):
            path_summaries.append(
                {
                    "rank": idx,
                    "length": p["length"],
                    "node_ids": p["node_ids"],
                    "avg_confidence": p["avg_confidence"],
                    "score": p["score"],
                }
            )

        node_ids = list(dict.fromkeys(node_ids))[:node_budget]
        node_rows = self.graph_client.execute_query(
            """
            MATCH (n)
            WHERE n.id IN $ids
            RETURN n
            """,
            {"ids": node_ids},
        )
        nodes = [self._node_to_dto(r["n"]) for r in node_rows]
        edges = [e for e in self._query_edges_between(node_ids, edge_budget) if e["type"] in rel_types]

        resp = self._build_view_response(
            project_id=project_id,
            task="path",
            nodes=nodes,
            edges=edges,
            budget=budget,
            focus_ids=[from_id, to_id],
            explanations=[f"路径分析 from={from_id} to={to_id}, 最多 {k_paths} 条。"],
            warnings=[] if path_summaries else ["未找到满足条件的路径。"],
            fast_mode=True,
        )
        resp["paths"] = path_summaries
        return resp

    def build_entry_flow_view(
        self,
        project: str,
        entry_id: str | None = None,
        max_steps: int = 12,
        node_budget: int | None = None,
        edge_budget: int | None = None,
        auto_budget: bool = True,
    ) -> Dict[str, Any]:
        project_id = self._project_id(project)

        if auto_budget and (node_budget is None or edge_budget is None):
            stats = self._get_graph_stats(project_id)
            budget = self.calculate_adaptive_budget(stats["total_nodes"], stats["total_edges"], "entry_flow")
            node_budget, edge_budget = budget.node_budget, budget.edge_budget
        else:
            node_budget = node_budget or 700
            edge_budget = edge_budget or 1400

        budget = Budget(node_budget=node_budget, edge_budget=edge_budget)

        if entry_id:
            entry_rows = self.graph_client.execute_query("MATCH (n) WHERE n.id = $id RETURN n", {"id": entry_id})
        else:
            entry_rows = self.graph_client.execute_query(
                """
                MATCH (p:Project)
                WHERE p.id = $project_id
                MATCH (p)-[:CONTAINS|DEFINES*]->(n)
                WHERE toLower(coalesce(n.name, '')) CONTAINS 'handler'
                   OR toLower(coalesce(n.name, '')) CONTAINS 'controller'
                   OR toLower(coalesce(n.name, '')) CONTAINS 'route'
                RETURN n
                LIMIT 1
                """,
                {"project_id": project_id},
            )

        if not entry_rows:
            return self._build_view_response(
                project_id=project_id,
                task="entry_flow",
                nodes=[],
                edges=[],
                budget=budget,
                focus_ids=[],
                explanations=["未找到入口节点。"],
                warnings=["请指定 entry_id 或补充入口检测规则。"],
                fast_mode=True,
            )

        entry_node = self._node_to_dto(entry_rows[0]["n"])
        entry_id = entry_node["id"]

        # Memgraph 不支持参数化路径长度，将 max_steps 内联到查询中
        steps = int(max_steps)
        rows = self.graph_client.execute_query(
            f"""
            MATCH (entry)
            WHERE entry.id = $entry_id
            MATCH p = (entry)-[:CALLS|IMPORTS|REFERENCES*1..{steps}]->(n)
            UNWIND nodes(p) AS nd
            WITH DISTINCT nd
            RETURN nd AS n
            LIMIT $node_budget
            """,
            {
                "entry_id": entry_id,
                "node_budget": node_budget,
            },
        )
        nodes = [self._node_to_dto(r["n"]) for r in rows]
        if entry_id not in {n["id"] for n in nodes}:
            nodes.insert(0, entry_node)

        edges = self._query_edges_between([n["id"] for n in nodes], edge_budget)
        edges = [e for e in edges if e["type"] in {"CALLS", "IMPORTS", "REFERENCES"}]

        return self._build_view_response(
            project_id=project_id,
            task="entry_flow",
            nodes=nodes,
            edges=edges,
            budget=budget,
            focus_ids=[entry_id],
            explanations=[f"入口流程分析: {entry_id}, 最大步骤 {max_steps}。"],
            warnings=[],
            fast_mode=True,
        )

    def get_analysis_status(self, project: str, fast_mode: bool = True) -> Dict[str, Any]:
        project_id = self._project_id(project)
        node_count_rows = self.graph_client.execute_query(
            """
            MATCH (p:Project)
            WHERE p.id = $project_id
            MATCH (p)-[:CONTAINS|DEFINES*]->(n)
            WHERE NOT n:Project
            RETURN count(DISTINCT n) AS total
            """,
            {"project_id": project_id},
        )
        total_nodes = int(node_count_rows[0].get("total", 0)) if node_count_rows else 0

        if fast_mode:
            community_rows = []
            process_rows = []
        else:
            community_rows = self.graph_client.execute_query(
                """
                MATCH (p:Project)
                WHERE p.id = $project_id
                MATCH (p)-[:CONTAINS|DEFINES*]->(n)
                WHERE n:Community
                RETURN count(DISTINCT n) AS total
                """,
                {"project_id": project_id},
            )
            process_rows = self.graph_client.execute_query(
                """
                MATCH (p:Project)
                WHERE p.id = $project_id
                MATCH (p)-[:CONTAINS|DEFINES*]->(n)
                WHERE n:Process
                RETURN count(DISTINCT n) AS total
                """,
                {"project_id": project_id},
            )

        community_count = int(community_rows[0].get("total", 0)) if community_rows else 0
        process_count = int(process_rows[0].get("total", 0)) if process_rows else 0

        ready_features = ["overview", "impact", "path", "entry_flow"]
        if community_count > 0:
            ready_features.append("community")
        if process_count > 0:
            ready_features.append("process")

        return {
            "snapshot_version": "v0",
            "project": project,
            "stages": {
                "ingestion": "ready" if total_nodes > 0 else "empty",
                "community": "ready" if community_count > 0 else "not_ready",
                "process": "ready" if process_count > 0 else "not_ready",
            },
            "progress": 100 if total_nodes > 0 else 0,
            "ready_features": ready_features,
            "stats": {
                "total_nodes": total_nodes,
                "communities": community_count,
                "processes": process_count,
            },
        }
