"""DeepResearch 引擎 — 图谱驱动的迭代式深度研究"""

import json
import uuid
from typing import List, Dict, Any

from loguru import logger

from src.rag.llm_client import LLMClient
from src.rag.retriever import HybridRetriever
from src.graph.client import GraphClient
from src.rag.conversation import ConversationMemory
from src.research.models import ResearchSession, ResearchIteration
from src.research.prompts import (
    RESEARCH_FIRST_PROMPT,
    RESEARCH_INTERMEDIATE_PROMPT,
    RESEARCH_FINAL_PROMPT,
)


class ResearchEngine:
    """图谱驱动的迭代式深度研究引擎"""

    def __init__(
        self,
        llm_client: LLMClient,
        retriever: HybridRetriever,
        graph_client: GraphClient,
        conversation_memory: ConversationMemory,
    ):
        self.llm = llm_client
        self.retriever = retriever
        self.graph = graph_client
        self.memory = conversation_memory

    # ── public API ──────────────────────────────────────────────

    async def start_research(self, query: str, project_id: str) -> ResearchSession:
        """创建研究会话并执行首轮迭代"""
        session = ResearchSession(
            id=str(uuid.uuid4()),
            project_id=project_id,
            original_query=query,
        )
        session = await self._run_iteration(session, is_first=True)
        await self._save_session(session)
        return session

    async def continue_research(self, session: ResearchSession) -> ResearchSession:
        """执行下一轮迭代"""
        if session.status == "concluded":
            logger.warning(f"Session {session.id} already concluded")
            return session
        if len(session.iterations) >= session.max_iterations:
            return await self.conclude_research(session)
        session = await self._run_iteration(session, is_first=False)
        await self._save_session(session)
        return session

    async def conclude_research(self, session: ResearchSession) -> ResearchSession:
        """强制执行最终总结迭代"""
        session = await self._run_iteration(session, is_first=False, is_final=True)
        session.status = "concluded"
        await self._save_session(session)
        return session

    # ── iteration core ──────────────────────────────────────────

    async def _run_iteration(
        self,
        session: ResearchSession,
        is_first: bool = False,
        is_final: bool = False,
    ) -> ResearchSession:
        """执行单次研究迭代"""
        iteration_num = len(session.iterations) + 1
        graph_project_id = self._normalize_project_id(session.project_id)

        # a. 规划探索方向 — 找到未探索的图谱邻居
        explore_entities = self._plan_next_exploration(session)

        # b. 图谱遍历 — 获取相关实体的 1-hop 邻居
        graph_context = await self._graph_traverse(
            graph_project_id, explore_entities
        )

        # c. 检索代码上下文
        search_query = (
            session.original_query
            if is_first
            else f"{session.original_query} {' '.join(explore_entities[:3])}"
        )
        retrieval = await self.retriever.retrieve(
            query=search_query, project_id=graph_project_id, k=10
        )
        code_context = self._format_code_context(retrieval.contexts)

        # d. 选择提示词并生成发现
        prompt = self._build_prompt(
            session, graph_context, code_context,
            explore_entities, iteration_num,
            is_first=is_first, is_final=is_final,
        )
        findings = await self.llm.chat_completion(
            [{"role": "user", "content": prompt}],
            max_tokens=3000,
        )

        # e. 记录迭代
        explored_ids = [e.get("id", "") for e in graph_context]
        iteration = ResearchIteration(
            iteration=iteration_num,
            query=search_query,
            findings=findings,
            graph_entities_explored=explored_ids,
            sources=retrieval.contexts[:5],
        )
        session.iterations.append(iteration)

        logger.info(
            f"Research iteration {iteration_num} done for session {session.id}, "
            f"explored {len(explored_ids)} entities"
        )
        return session

    # ── exploration planning ────────────────────────────────────

    def _plan_next_exploration(self, session: ResearchSession) -> List[str]:
        """图谱驱动的探索规划 — 找到未探索的 1-hop 邻居"""
        if not session.iterations:
            return []

        # 收集已探索的实体 ID
        explored: set[str] = set()
        for it in session.iterations:
            explored.update(it.graph_entities_explored)

        # 从最近一轮的来源中提取候选实体名
        last = session.iterations[-1]
        candidates: List[str] = []
        for src in last.sources:
            meta = src.get("metadata", {})
            name = meta.get("name") or meta.get("text", "")[:60]
            if name and name not in explored:
                candidates.append(name)

        return candidates[:5]

    # ── graph traversal ─────────────────────────────────────────

    async def _graph_traverse(
        self, project_id: str, entity_names: List[str]
    ) -> List[Dict[str, Any]]:
        """获取实体的 1-hop 邻居和跨社区连接"""
        if not entity_names:
            return []

        cypher = """
        MATCH (p:Project {id: $project_id})-[:CONTAINS*]->(n)
        WHERE n.name IN $names
        WITH n
        MATCH (n)-[r]-(neighbor)
        RETURN DISTINCT neighbor.id AS id,
               neighbor.name AS name,
               labels(neighbor)[0] AS label,
               type(r) AS rel_type
        LIMIT 20
        """
        try:
            results = self.graph.execute_query(
                cypher, {"project_id": project_id, "names": entity_names}
            )
            return results
        except Exception as e:
            logger.error(f"Graph traversal failed: {e}")
            return []

    # ── prompt building ─────────────────────────────────────────

    def _build_prompt(
        self,
        session: ResearchSession,
        graph_context: List[Dict[str, Any]],
        code_context: str,
        explore_entities: List[str],
        iteration_num: int,
        is_first: bool = False,
        is_final: bool = False,
    ) -> str:
        """根据迭代阶段选择并填充提示词"""
        graph_text = self._format_graph_context(graph_context)

        if is_final:
            all_findings = "\n\n".join(
                f"--- 第 {it.iteration} 轮 ---\n{it.findings}"
                for it in session.iterations
            )
            all_explored = set()
            for it in session.iterations:
                all_explored.update(it.graph_entities_explored)
            return RESEARCH_FINAL_PROMPT.format(
                query=session.original_query,
                all_findings=all_findings,
                explored_entities=", ".join(all_explored),
                graph_relationships=graph_text,
            )

        if is_first:
            return RESEARCH_FIRST_PROMPT.format(
                query=session.original_query,
                graph_context=graph_text,
                code_context=code_context,
            )

        # intermediate
        previous_findings = session.iterations[-1].findings if session.iterations else ""
        return RESEARCH_INTERMEDIATE_PROMPT.format(
            iteration=iteration_num,
            query=session.original_query,
            previous_findings=previous_findings,
            entities=", ".join(explore_entities),
            graph_context=graph_text,
            code_context=code_context,
        )

    # ── formatting helpers ──────────────────────────────────────

    @staticmethod
    def _format_graph_context(entities: List[Dict[str, Any]]) -> str:
        """将图谱实体列表格式化为文本"""
        if not entities:
            return "(无图谱上下文)"
        lines = []
        for e in entities:
            lines.append(
                f"- {e.get('name', '?')} [{e.get('label', '?')}] "
                f"--{e.get('rel_type', '?')}--> ..."
            )
        return "\n".join(lines)

    @staticmethod
    def _format_code_context(contexts: List[Dict[str, Any]]) -> str:
        """将检索结果格式化为代码上下文文本"""
        if not contexts:
            return "(无代码上下文)"
        parts = []
        for i, ctx in enumerate(contexts[:8], 1):
            text = ctx.get("text", ctx.get("metadata", {}).get("text", ""))
            source = ctx.get("source", "unknown")
            parts.append(f"[{i}] ({source}) {text[:500]}")
        return "\n\n".join(parts)

    @staticmethod
    def _normalize_project_id(project_id: str) -> str:
        """统一 project_id 格式"""
        if project_id.startswith("project:"):
            return project_id
        return f"project:{project_id}"

    # ── session persistence (Redis) ─────────────────────────────

    async def _save_session(self, session: ResearchSession) -> None:
        """将会话状态存储到 Redis"""
        key = f"research:{session.project_id}:{session.id}"
        data = session.model_dump_json()
        await self.memory.redis.set(key, data, ex=7200)
        logger.debug(f"Saved research session {key}")

    async def load_session(self, project_id: str, session_id: str) -> ResearchSession:
        """从 Redis 加载会话状态"""
        key = f"research:{project_id}:{session_id}"
        raw = await self.memory.redis.get(key)
        if raw is None:
            raise ValueError(f"Research session not found: {key}")
        return ResearchSession.model_validate_json(raw)
