"""Wiki 结构分析器 — 从图谱社区检测结果生成 Wiki 骨架"""

import json
import uuid
from typing import Any, Dict, List, Tuple
from loguru import logger

from src.graph.client import GraphClient
from src.rag.llm_client import LLMClient
from src.wiki.models import WikiStructure, WikiSection, WikiPage
from src.wiki.prompts import WIKI_STRUCTURE_REVIEW_PROMPT


class WikiStructureAnalyzer:
    """从知识图谱社区结构生成 Wiki 骨架"""

    def __init__(self, graph_client: GraphClient, llm_client: LLMClient, project_id: str):
        self.graph_client = graph_client
        self.llm_client = llm_client
        self.project_id = project_id

    async def analyze_structure(self) -> WikiStructure:
        """分析图谱结构，生成 Wiki 骨架（无内容）"""
        logger.info(f"Analyzing wiki structure for project {self.project_id}")

        # Step a: 按社区分组节点
        communities = self._query_communities()
        if not communities:
            logger.warning("No communities found, creating single-section wiki")
            communities = {0: self._query_all_nodes()}

        # Step b: 每个社区找 hub 节点作为候选页面
        sections: Dict[str, WikiSection] = {}
        pages: Dict[str, WikiPage] = {}

        ranked_cids = self._rank_communities(communities)

        for cid in ranked_cids:
            nodes = communities[cid]
            key_entities = self._identify_key_entities(cid)
            section_id = f"section_{cid}"

            page_ids: List[str] = []
            for entity in key_entities:
                page_id = f"page_{entity['id'].replace(':', '_')}"
                pages[page_id] = WikiPage(
                    id=page_id,
                    title=entity.get("name", page_id),
                    file_paths=[entity.get("file_path", "")] if entity.get("file_path") else [],
                    importance=entity.get("degree", 0.0),
                    graph_entity_ids=[entity["id"]],
                )
                page_ids.append(page_id)

            sections[section_id] = WikiSection(
                id=section_id,
                title=f"Community {cid}",
                pages=page_ids,
                community_id=cid,
            )

        # Step c: 分析社区间边密度 → 章节层级
        cross_edges = self._query_cross_community_edges()
        self._build_section_hierarchy(sections, cross_edges)

        # Step d: 识别入口点
        entry_points = self._find_entry_points()
        for ep in entry_points:
            page_id = f"page_{ep['id'].replace(':', '_')}"
            if page_id not in pages:
                pages[page_id] = WikiPage(
                    id=page_id,
                    title=ep.get("name", page_id),
                    importance=1.0,
                    graph_entity_ids=[ep["id"]],
                )

        # Step e: LLM 审查结构
        sections, pages = await self._llm_review_structure(sections, pages)

        root_section_ids = [s.id for s in sections.values() if not any(
            s.id in other.subsections for other in sections.values()
        )]

        wiki = WikiStructure(
            id=f"wiki_{self.project_id}",
            title=f"{self.project_id} Documentation",
            description="Auto-generated project documentation",
            pages=pages,
            sections=sections,
            root_sections=root_section_ids,
            project_id=self.project_id,
        )
        logger.info(
            f"Wiki structure: {len(sections)} sections, {len(pages)} pages, "
            f"{len(root_section_ids)} root sections"
        )
        return wiki

    # ------------------------------------------------------------------
    # Graph queries
    # ------------------------------------------------------------------

    def _query_communities(self) -> Dict[int, List[Dict[str, Any]]]:
        """查询所有社区及其节点"""
        query = (
            "MATCH (n) WHERE n.project_id = $pid AND n.community_id IS NOT NULL "
            "RETURN n.community_id AS cid, "
            "collect({id: n.id, name: n.name, label: labels(n)[0], "
            "file_path: n.file_path}) AS nodes"
        )
        rows = self.graph_client.execute_query(query, {"pid": self.project_id})
        return {r["cid"]: r["nodes"] for r in rows}

    def _query_all_nodes(self) -> List[Dict[str, Any]]:
        """回退：查询项目所有节点"""
        query = (
            "MATCH (n) WHERE n.project_id = $pid "
            "RETURN n.id AS id, n.name AS name, labels(n)[0] AS label, "
            "n.file_path AS file_path LIMIT 200"
        )
        return self.graph_client.execute_query(query, {"pid": self.project_id})

    def _query_cross_community_edges(self) -> List[Dict[str, Any]]:
        """查询社区间边密度"""
        query = (
            "MATCH (a)-[r]->(b) "
            "WHERE a.project_id = $pid AND b.project_id = $pid "
            "AND a.community_id <> b.community_id "
            "RETURN a.community_id AS from_cid, b.community_id AS to_cid, "
            "type(r) AS rel, count(*) AS weight"
        )
        return self.graph_client.execute_query(query, {"pid": self.project_id})

    def _find_entry_points(self) -> List[Dict[str, Any]]:
        """识别入口点 (main/init 模式 + 高入度节点)"""
        query = (
            "MATCH (n) WHERE n.project_id = $pid "
            "WHERE n.name CONTAINS 'main' OR n.name CONTAINS 'init' "
            "   OR n.name CONTAINS 'Main' OR n.name CONTAINS 'Init' "
            "RETURN n.id AS id, n.name AS name LIMIT 10"
        )
        results = self.graph_client.execute_query(query, {"pid": self.project_id})
        # 补充高入度节点
        in_degree_query = (
            "MATCH (n)<-[r]-() WHERE n.project_id = $pid "
            "RETURN n.id AS id, n.name AS name, count(r) AS deg "
            "ORDER BY deg DESC LIMIT 5"
        )
        results.extend(self.graph_client.execute_query(in_degree_query, {"pid": self.project_id}))
        # 去重
        seen = set()
        unique: List[Dict[str, Any]] = []
        for r in results:
            if r["id"] not in seen:
                seen.add(r["id"])
                unique.append(r)
        return unique

    # ------------------------------------------------------------------
    # Ranking & analysis
    # ------------------------------------------------------------------

    def _rank_communities(
        self, communities: Dict[int, List[Dict[str, Any]]]
    ) -> List[int]:
        """按连通性和入口点排序社区"""
        scores: Dict[int, float] = {}
        for cid, nodes in communities.items():
            size = len(nodes)
            # 检查是否包含入口点
            has_entry = any(
                "main" in (n.get("name") or "").lower()
                or "init" in (n.get("name") or "").lower()
                for n in nodes
            )
            scores[cid] = size + (100.0 if has_entry else 0.0)
        return sorted(scores, key=scores.get, reverse=True)

    def _identify_key_entities(self, community_id: int) -> List[Dict[str, Any]]:
        """使用度中心性找出社区核心实体"""
        query = (
            "MATCH (n)-[r]-() WHERE n.project_id = $pid AND n.community_id = $cid "
            "RETURN n.id AS id, n.name AS name, n.file_path AS file_path, "
            "count(r) AS degree "
            "ORDER BY degree DESC LIMIT 10"
        )
        return self.graph_client.execute_query(
            query, {"pid": self.project_id, "cid": community_id}
        )

    def _build_section_hierarchy(
        self,
        sections: Dict[str, WikiSection],
        cross_edges: List[Dict[str, Any]],
    ) -> None:
        """根据社区间边密度构建章节父子关系（就地修改 sections）"""
        # 统计社区对之间的总权重
        pair_weight: Dict[Tuple[int, int], int] = {}
        for edge in cross_edges:
            pair = (edge["from_cid"], edge["to_cid"])
            pair_weight[pair] = pair_weight.get(pair, 0) + edge["weight"]

        # 如果小社区对大社区有高密度依赖，将其设为子章节
        section_by_cid = {s.community_id: s for s in sections.values() if s.community_id is not None}
        for (from_cid, to_cid), weight in sorted(pair_weight.items(), key=lambda x: x[1], reverse=True):
            from_sec = section_by_cid.get(from_cid)
            to_sec = section_by_cid.get(to_cid)
            if not from_sec or not to_sec:
                continue
            # 小社区依赖大社区 → 小社区成为大社区的子章节
            if len(from_sec.pages) < len(to_sec.pages) and weight >= 3:
                if from_sec.id not in to_sec.subsections:
                    to_sec.subsections.append(from_sec.id)

    # ------------------------------------------------------------------
    # LLM review
    # ------------------------------------------------------------------

    async def _llm_review_structure(
        self,
        sections: Dict[str, WikiSection],
        pages: Dict[str, WikiPage],
    ) -> Tuple[Dict[str, WikiSection], Dict[str, WikiPage]]:
        """让 LLM 审查并优化 Wiki 结构（重命名、合并、拆分）"""
        candidate = {
            sid: {"title": s.title, "page_count": len(s.pages), "community_id": s.community_id}
            for sid, s in sections.items()
        }
        node_names = {
            sid: [pages[pid].title for pid in s.pages if pid in pages]
            for sid, s in sections.items()
        }

        prompt = WIKI_STRUCTURE_REVIEW_PROMPT.format(
            candidate_structure=json.dumps(candidate, indent=2),
            node_names_by_section=json.dumps(node_names, indent=2),
        )

        try:
            response = await self.llm_client.chat_completion(
                [{"role": "user", "content": prompt}], max_tokens=2000
            )
            # 提取 JSON
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                review = json.loads(response[start:end])
            else:
                logger.warning("LLM review response has no JSON, skipping")
                return sections, pages

            for item in review.get("sections", []):
                sid = item.get("id")
                if sid and sid in sections:
                    if item.get("title"):
                        sections[sid].title = item["title"]
                    if item.get("merge_into") and item["merge_into"] in sections:
                        target = sections[item["merge_into"]]
                        target.pages.extend(sections[sid].pages)
                        del sections[sid]

        except Exception as e:
            logger.warning(f"LLM structure review failed: {e}, using raw structure")

        return sections, pages
