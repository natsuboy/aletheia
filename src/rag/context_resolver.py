"""多轮上下文解析 — 代词消解 + 实体映射"""

import re
from typing import List, Dict, Optional
from loguru import logger

from src.rag.conversation import DialogTurn


class ContextResolver:
    """解析多轮对话中的代词引用，映射到前轮图实体"""

    # 中英文代词 → 需要回溯的信号词
    PRONOUN_PATTERNS = [
        "它", "它们", "这个", "那个", "该", "上面的", "前面的",
        "this", "that", "it", "them", "these", "those",
        "the same", "above", "previous",
    ]

    RELATION_KEYWORDS = [
        "调用者", "被调用者", "caller", "callee",
        "父类", "子类", "parent", "child",
        "依赖", "依赖它的", "depends on", "depended by",
        "谁调用了", "谁使用了", "who calls", "who uses",
    ]

    def resolve(
        self,
        current_query: str,
        history: List[DialogTurn],
    ) -> str:
        """用历史实体上下文增强当前查询

        Returns:
            增强后的查询字符串
        """
        if not history:
            return current_query

        needs_resolution = self._needs_resolution(current_query)
        if not needs_resolution:
            return current_query

        # 收集前轮提到的实体 ID
        recent_entity_ids = self._collect_recent_entities(history, n=3)
        if not recent_entity_ids:
            return current_query

        # 构建增强查询
        entity_context = ", ".join(recent_entity_ids[:10])
        enhanced = (
            f"{current_query}\n\n"
            f"[上下文: 前轮对话涉及的图实体 ID: {entity_context}]"
        )
        logger.info(
            f"ContextResolver enhanced query with {len(recent_entity_ids)} entities"
        )
        return enhanced

    def get_recent_entity_ids(
        self,
        history: List[DialogTurn],
        n: int = 3,
    ) -> List[str]:
        """获取最近 n 轮的实体 ID（供 retriever 使用）"""
        return self._collect_recent_entities(history, n)

    def _needs_resolution(self, query: str) -> bool:
        """判断查询是否包含需要消解的代词/关系词"""
        q_lower = query.lower()
        for pattern in self.PRONOUN_PATTERNS:
            if pattern.isascii():
                if re.search(r'\b' + re.escape(pattern.lower()) + r'\b', q_lower):
                    return True
            else:
                if pattern in q_lower:
                    return True
        for kw in self.RELATION_KEYWORDS:
            if kw.isascii():
                if re.search(r'\b' + re.escape(kw.lower()) + r'\b', q_lower):
                    return True
            else:
                if kw in q_lower:
                    return True
        return False

    def _collect_recent_entities(
        self,
        history: List[DialogTurn],
        n: int,
    ) -> List[str]:
        """从最近 n 轮收集实体 ID（去重保序）"""
        seen = set()
        result = []
        for turn in reversed(history[-n:]):
            for eid in turn.retrieved_entity_ids:
                if eid not in seen:
                    seen.add(eid)
                    result.append(eid)
        return result
