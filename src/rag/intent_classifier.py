"""查询意图分类器"""
from enum import Enum
from typing import Dict, List, Tuple
from dataclasses import dataclass
from loguru import logger


class QueryIntent(str, Enum):
    """查询意图枚举"""
    ARCHITECTURE = "architecture"      # 架构查询
    IMPLEMENTATION = "implementation"  # 实现细节
    DEBUGGING = "debugging"            # 调试问题
    RELATION = "relation"              # 关系查询
    REFERENCE = "reference"            # 引用查找


@dataclass
class IntentClassification:
    """意图分类结果"""
    intent: QueryIntent
    confidence: float  # 0-1
    vector_weight: float  # 向量检索权重
    graph_weight: float   # 图谱检索权重


class IntentClassifier:
    """轻量级意图分类器 (基于关键词规则)"""

    # 关键词规则库
    KEYWORD_RULES: Dict[QueryIntent, List[str]] = {
        QueryIntent.ARCHITECTURE: [
            "架构", "结构", "设计", "模块", "组件", "层次",
            "architecture", "structure", "design", "module", "component",
            "整体", "全局", "系统", "概览", "框架"
        ],
        QueryIntent.IMPLEMENTATION: [
            "如何实现", "怎么做", "实现方式", "代码", "函数", "方法",
            "how to", "implement", "code", "function", "method",
            "写", "创建", "开发", "编写"
        ],
        QueryIntent.DEBUGGING: [
            "错误", "异常", "bug", "问题", "失败", "崩溃",
            "error", "exception", "fail", "crash", "issue",
            "为什么", "why", "原因", "调试", "debug"
        ],
        QueryIntent.RELATION: [
            "关系", "依赖", "调用", "继承", "实现",
            "relation", "dependency", "call", "inherit", "implement",
            "之间", "between", "连接", "关联", "引用"
        ],
        QueryIntent.REFERENCE: [
            "哪里用到", "被引用", "使用", "调用",
            "where", "used", "reference", "call",
            "查找", "find", "搜索", "search"
        ]
    }

    # 意图对应的权重 (vector_weight, graph_weight)
    WEIGHTS: Dict[QueryIntent, Tuple[float, float]] = {
        QueryIntent.ARCHITECTURE: (0.3, 0.7),   # 架构查询更依赖图谱
        QueryIntent.IMPLEMENTATION: (0.6, 0.4),  # 实现细节更依赖向量
        QueryIntent.DEBUGGING: (0.6, 0.4),       # 调试更依赖向量
        QueryIntent.RELATION: (0.2, 0.8),        # 关系查询高度依赖图谱
        QueryIntent.REFERENCE: (0.6, 0.4)        # 引用查找混合
    }

    def classify(self, query: str) -> IntentClassification:
        """
        分类查询意图 (基于关键词匹配)

        Args:
            query: 用户查询

        Returns:
            意图分类结果
        """
        query_lower = query.lower()

        # 计算每个意图的匹配分数
        scores = {}
        for intent, keywords in self.KEYWORD_RULES.items():
            score = sum(1 for kw in keywords if kw in query_lower)
            scores[intent] = score

        # 找到最高分意图
        max_intent = max(scores, key=lambda x: scores[x])
        max_score = scores[max_intent]

        # 计算置信度
        total_score = sum(scores.values())
        confidence = max_score / (total_score + 1e-6) if total_score > 0 else 0.0

        # 如果所有分数都很低,默认为 IMPLEMENTATION
        if max_score == 0:
            max_intent = QueryIntent.IMPLEMENTATION
            confidence = 0.3

        # 获取权重
        vector_weight, graph_weight = self.WEIGHTS[max_intent]

        logger.info(
            f"Classified intent: {max_intent.value} "
            f"(confidence={confidence:.2f}, "
            f"vector_weight={vector_weight}, graph_weight={graph_weight})"
        )

        return IntentClassification(
            intent=max_intent,
            confidence=confidence,
            vector_weight=vector_weight,
            graph_weight=graph_weight
        )
