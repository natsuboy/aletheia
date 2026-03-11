"""图谱上下文检索器"""
from typing import List, Dict, Any
from dataclasses import dataclass, field
import re
from loguru import logger

from src.graph import GraphClient


@dataclass
class GraphContext:
    """图谱上下文"""
    entities: List[Dict[str, Any]] = field(default_factory=list)
    relationships: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class GraphRetriever:
    """图谱上下文检索器"""

    def __init__(self, graph_client: GraphClient):
        """
        初始化图谱检索器

        Args:
            graph_client: Memgraph 客户端
        """
        self.graph_client = graph_client

    # 常见非实体词
    _STOP_WORDS = {
        "User", "API", "GET", "POST", "PUT", "DELETE",
        "The", "This", "That", "What", "How", "Why", "Where", "When",
        "Which", "Does", "Can", "Could", "Would", "Should", "Is", "Are",
        "Was", "Were", "Has", "Have", "Had", "Do", "Did", "Will",
        "From", "With", "About", "Into", "For", "And", "But", "Not",
        "Explain", "Show", "Tell", "Find", "List", "Describe", "Return",
        "Give", "Make", "Use", "Call", "Run", "Check", "Look",
    }

    def _extract_entities(self, query: str) -> List[str]:
        """
        从查询中提取实体关键词（支持 PascalCase、snake_case、camelCase、点分路径）
        """
        candidates: List[str] = []

        # PascalCase / 大写开头
        candidates.extend(re.findall(r'\b[A-Z][a-zA-Z0-9_]*\b', query))
        # snake_case (至少 3 字符，含下划线)
        candidates.extend(re.findall(r'\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b', query))
        # camelCase
        candidates.extend(re.findall(r'\b[a-z]+[A-Z][a-zA-Z0-9]*\b', query))
        # 点分路径 (如 module.ClassName)
        candidates.extend(re.findall(r'\b[a-zA-Z_]\w*(?:\.\w+)+\b', query))

        # 先过滤 stop_words，再去重保序
        filtered = [e for e in candidates if e not in self._STOP_WORDS]
        seen: set = set()
        entities: List[str] = []
        for e in filtered:
            if e not in seen:
                seen.add(e)
                entities.append(e)

        logger.info(f"Extracted entities: {entities}")
        return entities

    async def retrieve(
        self,
        query: str,
        project_id: str,
        hops: int = 2
    ) -> GraphContext:
        """
        检索图谱上下文

        Args:
            query: 用户查询
            project_id: 项目 ID
            hops: 图遍历跳数

        Returns:
            图谱上下文
        """
        # 提取实体关键词
        entities = self._extract_entities(query)

        if not entities:
            logger.info("No entities extracted, returning empty context")
            return GraphContext()

        # 构建查询：模糊匹配实体名称 + 双向邻居遍历
        cypher = """
        MATCH (p:Project {id: $project_id})-[:CONTAINS*]->(n)
        WHERE ANY(kw IN $keywords WHERE toLower(n.name) CONTAINS toLower(kw))
        WITH n
        MATCH (n)-[r]-(neighbor)
        RETURN n as entity, labels(n)[0] as entity_label, collect(DISTINCT {
            id: neighbor.id,
            name: neighbor.name,
            label: labels(neighbor)[0],
            rel_type: type(r)
        }) as neighbors
        LIMIT 10
        """

        try:
            results = self.graph_client.execute_query(
                cypher,
                {
                    "project_id": project_id,
                    "keywords": entities
                }
            )

            # 构建上下文
            context_entities = []
            relationships = []

            for record in results:
                entity = record.get("entity")
                neighbors = record.get("neighbors", [])

                if entity:
                    context_entities.append({
                        "id": entity.get("id"),
                        "name": entity.get("name"),
                        "type": record.get("entity_label") or "Unknown"
                    })

                    # 添加关系
                    for neighbor in neighbors:
                        relationships.append({
                            "from": entity.get("name"),
                            "to": neighbor.get("name"),
                            "type": neighbor.get("rel_type")
                        })

            logger.info(
                f"Retrieved graph context: "
                f"{len(context_entities)} entities, "
                f"{len(relationships)} relationships"
            )

            return GraphContext(
                entities=context_entities,
                relationships=relationships,
                metadata={"query_entities": entities}
            )

        except Exception as e:
            logger.error(f"Failed to retrieve graph context: {e}")
            return GraphContext()
