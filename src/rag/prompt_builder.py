"""提示词构建器"""
from typing import List, Dict, Any, Optional
from loguru import logger

from src.rag.retriever import RetrievalResult
from src.rag.graph_retriever import GraphContext
from src.rag.conversation import DialogTurn


class PromptBuilder:
    """提示词构建器"""

    # 字符数与 token 数的估算比例 (约 4 字符/token)
    CHARS_PER_TOKEN = 4

    def __init__(self, max_context_tokens: int = 8000):
        self.max_context_tokens = max_context_tokens

    SYSTEM_PROMPT = """你是一个专业的代码助手,帮助开发者理解代码库。

你的任务:
1. 基于提供的代码片段和图谱关系回答用户问题
2. 回答要准确、清晰、简洁
3. 如果信息不足,明确说明
4. 引用代码时使用 [[file_path:start_line-end_line]] 格式（如 [[src/main.py:10-25]]）
5. 引用代码实体时使用 [[Type:Name]] 格式（如 [[Function:parse_config]]、[[Class:GraphClient]]）

重要规则:
- 只基于给定的上下文回答
- 不要编造不存在的代码或关系
- 代码片段用代码块标记
- 明确引用图谱关系 (如 "根据调用图...")
- 尽量使用 [[]] 引用格式，让用户可以点击跳转到对应代码
"""

    def build_system_prompt(self) -> str:
        """
        构建系统提示词

        Returns:
            系统提示词
        """
        return self.SYSTEM_PROMPT

    def build_user_prompt(
        self,
        query: str,
        retrieval_result: RetrievalResult
    ) -> str:
        """
        构建用户提示词

        Args:
            query: 用户查询
            retrieval_result: 检索结果

        Returns:
            用户提示词
        """
        # 格式化代码上下文
        code_contexts = self._format_code_contexts(retrieval_result.contexts)

        # 格式化图谱上下文
        graph_context = self._format_graph_context(retrieval_result.graph_context)

        # 组合提示词
        prompt_parts = []

        if code_contexts:
            prompt_parts.append("## 相关代码片段\n\n" + code_contexts)

        if graph_context:
            prompt_parts.append("## 图谱关系\n\n" + graph_context)

        prompt_parts.append(f"## 用户问题\n\n{query}")

        prompt = "\n\n".join(prompt_parts)

        logger.info(f"Built prompt: {len(prompt)} chars")

        return prompt

    def _format_code_contexts(
        self,
        contexts: List[Dict[str, Any]]
    ) -> str:
        """
        格式化代码上下文

        Args:
            contexts: 上下文列表

        Returns:
            格式化的代码上下文
        """
        if not contexts:
            return ""

        formatted = []
        used_chars = 0
        budget_chars = self.max_context_tokens * self.CHARS_PER_TOKEN

        for i, ctx in enumerate(contexts[:10], 1):  # 最多 10 个
            text = ctx.get("text", "")
            score = ctx.get("score", 0.0)
            source = ctx.get("source", "unknown")
            metadata = ctx.get("metadata", {}) or {}
            file_path = metadata.get("path", source)

            if not text:
                continue

            entry = (
                f"**片段 {i}** (相关度: {score:.2f}, 文件: {file_path})\n"
                f"```\n{text}\n```"
            )
            if used_chars + len(entry) > budget_chars:
                break
            formatted.append(entry)
            used_chars += len(entry)

        return "\n\n".join(formatted)

    def _format_graph_context(
        self,
        graph_context: GraphContext
    ) -> str:
        """
        格式化图谱上下文

        Args:
            graph_context: 图谱上下文

        Returns:
            格式化的图谱上下文
        """
        if not graph_context.entities and not graph_context.relationships:
            return ""

        formatted = []

        # 实体
        if graph_context.entities:
            entities_text = ", ".join([
                f"{e.get('name')} ({e.get('type')})"
                for e in graph_context.entities[:10]
            ])
            formatted.append(f"**核心实体**: {entities_text}")

        # 关系
        if graph_context.relationships:
            relations = []
            for rel in graph_context.relationships[:10]:
                from_name = rel.get("from", "?")
                to_name = rel.get("to", "?")
                rel_type = rel.get("type", "?")
                relations.append(f"- {from_name} --[{rel_type}]--> {to_name}")

            formatted.append("**关系图**:\n" + "\n".join(relations))

        return "\n\n".join(formatted)

    def build_messages_with_history(
        self,
        query: str,
        retrieval_result: RetrievalResult,
        history: Optional[List[DialogTurn]] = None,
    ) -> List[Dict[str, str]]:
        """构建含历史的完整 messages 数组

        在 max_context_tokens 预算内截断历史。
        """
        system_prompt = self.build_system_prompt()
        user_prompt = self.build_user_prompt(query, retrieval_result)

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_prompt},
        ]

        if history:
            budget_chars = (self.max_context_tokens // 2) * self.CHARS_PER_TOKEN
            used = 0
            history_msgs: List[Dict[str, str]] = []
            for turn in history:
                pair_len = len(turn.user_query) + len(turn.assistant_response)
                if used + pair_len > budget_chars:
                    break
                history_msgs.append({"role": "user", "content": turn.user_query})
                history_msgs.append({"role": "assistant", "content": turn.assistant_response})
                used += pair_len
            messages.extend(history_msgs)

        messages.append({"role": "user", "content": user_prompt})
        return messages
