"""Wiki 内容生成器 — 为每个 WikiPage 填充 Markdown 内容"""

import json
from typing import Any, Dict, List
from loguru import logger

from src.graph.client import GraphClient
from src.rag.llm_client import LLMClient
from src.rag.retriever import HybridRetriever
from src.wiki.models import WikiPage
from src.wiki.prompts import WIKI_PAGE_PROMPT, WIKI_DIAGRAM_PROMPT


class WikiContentGenerator:
    """为 WikiPage 生成 Markdown 内容和 Mermaid 图表"""

    def __init__(
        self,
        llm_client: LLMClient,
        graph_client: GraphClient,
        retriever: HybridRetriever,
    ):
        self.llm_client = llm_client
        self.graph_client = graph_client
        self.retriever = retriever

    async def generate_page_content(self, page: WikiPage, project_id: str) -> WikiPage:
        """为单个页面生成完整内容

        Steps:
            a. 查询图谱获取实体完整上下文
            b. 通过 HybridRetriever 检索相关代码片段
            c. 构建专用 prompt
            d. LLM 生成 Markdown + Mermaid
        """
        logger.info(f"Generating content for page: {page.title} ({page.id})")

        # Step a: 查询实体上下文
        entity_context = self._query_entity_context(page.graph_entity_ids, project_id)

        # Step b: 检索相关代码
        code_snippets = await self._retrieve_code(page.title, project_id)

        # Step c: 构建 prompt 并调用 LLM
        graph_relations = self._format_relations(entity_context.get("relationships", []))
        entity_summary = self._format_entities(entity_context.get("entities", []))

        prompt = WIKI_PAGE_PROMPT.format(
            entity_context=entity_summary,
            code_snippets=code_snippets,
            graph_relations=graph_relations,
        )

        content = await self.llm_client.chat_completion(
            [{"role": "user", "content": prompt}], max_tokens=3000
        )
        page.content = content

        # Step d: 生成 Mermaid 图表
        if entity_context.get("relationships"):
            diagram = await self._generate_mermaid_diagram(
                entity_context["entities"], entity_context["relationships"]
            )
            if diagram:
                page.mermaid_diagrams.append(diagram)

        # 填充关联页面（基于图谱邻居）
        neighbor_ids = [
            r.get("target_id", "") for r in entity_context.get("relationships", [])
        ]
        page.related_pages = [f"page_{nid.replace(':', '_')}" for nid in neighbor_ids[:5]]

        logger.info(f"Page '{page.title}' generated: {len(content)} chars, "
                     f"{len(page.mermaid_diagrams)} diagrams")
        return page

    # ------------------------------------------------------------------
    # Graph queries
    # ------------------------------------------------------------------

    def _query_entity_context(
        self, entity_ids: List[str], project_id: str
    ) -> Dict[str, Any]:
        """查询实体的完整上下文：调用者、被调用者、实现者、字段"""
        if not entity_ids:
            return {"entities": [], "relationships": []}

        entities: List[Dict[str, Any]] = []
        relationships: List[Dict[str, Any]] = []

        for eid in entity_ids:
            # 实体属性
            node_q = (
                "MATCH (n) WHERE n.id = $eid AND n.project_id = $pid "
                "RETURN n.id AS id, n.name AS name, labels(n)[0] AS label, "
                "n.file_path AS file_path, n.documentation AS doc"
            )
            rows = self.graph_client.execute_query(node_q, {"eid": eid, "pid": project_id})
            entities.extend(rows)

            # 出边关系（callees, imports, implements）
            out_q = (
                "MATCH (n)-[r]->(m) WHERE n.id = $eid AND n.project_id = $pid "
                "RETURN n.name AS source, type(r) AS rel, m.id AS target_id, "
                "m.name AS target LIMIT 20"
            )
            relationships.extend(
                self.graph_client.execute_query(out_q, {"eid": eid, "pid": project_id})
            )

            # 入边关系（callers）
            in_q = (
                "MATCH (m)-[r]->(n) WHERE n.id = $eid AND n.project_id = $pid "
                "RETURN m.name AS source, type(r) AS rel, n.id AS target_id, "
                "n.name AS target LIMIT 20"
            )
            relationships.extend(
                self.graph_client.execute_query(in_q, {"eid": eid, "pid": project_id})
            )

        return {"entities": entities, "relationships": relationships}

    # ------------------------------------------------------------------
    # Code retrieval
    # ------------------------------------------------------------------

    async def _retrieve_code(self, query: str, project_id: str) -> str:
        """通过 HybridRetriever 检索相关代码片段"""
        try:
            result = await self.retriever.retrieve(query=query, project_id=project_id, k=5)
            snippets: List[str] = []
            for ctx in result.contexts[:5]:
                text = ctx.get("text", "")
                if text:
                    snippets.append(f"```\n{text}\n```")
            return "\n\n".join(snippets) if snippets else "(No code snippets found)"
        except Exception as e:
            logger.warning(f"Code retrieval failed for '{query}': {e}")
            return "(Code retrieval unavailable)"

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_entities(entities: List[Dict[str, Any]]) -> str:
        """格式化实体列表为文本"""
        if not entities:
            return "(No entities)"
        lines: List[str] = []
        for e in entities:
            name = e.get("name", "?")
            label = e.get("label", "?")
            doc = e.get("doc", "")
            line = f"- {name} ({label})"
            if doc:
                line += f": {doc[:200]}"
            lines.append(line)
        return "\n".join(lines)

    @staticmethod
    def _format_relations(relationships: List[Dict[str, Any]]) -> str:
        """格式化关系列表为文本"""
        if not relationships:
            return "(No relationships)"
        lines: List[str] = []
        for r in relationships:
            src = r.get("source", "?")
            rel = r.get("rel", "?")
            tgt = r.get("target", "?")
            lines.append(f"- {src} --[{rel}]--> {tgt}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Mermaid diagram generation
    # ------------------------------------------------------------------

    async def _generate_mermaid_diagram(
        self,
        entities: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]],
    ) -> str:
        """从图谱关系生成 Mermaid 图表"""
        entity_text = self._format_entities(entities)
        rel_text = self._format_relations(relationships)

        prompt = WIKI_DIAGRAM_PROMPT.format(
            entities=entity_text,
            relationships=rel_text,
        )

        try:
            diagram = await self.llm_client.chat_completion(
                [{"role": "user", "content": prompt}], max_tokens=1000
            )
            # 清理可能的 markdown 包裹
            diagram = diagram.strip()
            if diagram.startswith("```"):
                lines = diagram.split("\n")
                lines = lines[1:]  # remove opening ```mermaid
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                diagram = "\n".join(lines)
            return diagram.strip()
        except Exception as e:
            logger.warning(f"Mermaid diagram generation failed: {e}")
            return ""
