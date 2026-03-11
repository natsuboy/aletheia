"""SCIP 数据模型"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List


class NodeLabel(str, Enum):
    """图节点类型"""

    PROJECT = "Project"
    FILE = "File"
    PACKAGE = "Package"
    MODULE = "Module"
    CLASS = "Class"
    STRUCT = "Struct"
    INTERFACE = "Interface"
    FUNCTION = "Function"
    METHOD = "Method"
    FIELD = "Field"
    VARIABLE = "Variable"
    CONSTANT = "Constant"
    TYPE_ALIAS = "TypeAlias"


class EdgeType(str, Enum):
    """图边类型"""

    CONTAINS = "CONTAINS"
    DEFINES = "DEFINES"
    CALLS = "CALLS"
    IMPORTS = "IMPORTS"
    INHERITS = "INHERITS"
    IMPLEMENTS = "IMPLEMENTS"
    REFERENCES = "REFERENCES"
    TYPE_OF = "TYPE_OF"
    OVERRIDES = "OVERRIDES"


@dataclass
class GraphNode:
    """图节点"""

    id: str
    label: NodeLabel
    properties: Dict[str, Any]

    def to_cypher_create(self) -> tuple[str, Dict[str, Any]]:
        """生成 Cypher CREATE 查询"""
        # 转换属性值为 Cypher 兼容格式
        props = {}
        for k, v in self.properties.items():
            if isinstance(v, (list, dict)):
                import json

                props[k] = json.dumps(v)
            else:
                props[k] = v

        query = f"MERGE (n:{self.label.value} {{id: $id}}) SET n += $props RETURN n"
        params = {"id": self.id, "props": props}
        return query, params


@dataclass
class GraphEdge:
    """图边"""

    from_id: str
    to_id: str
    type: EdgeType
    properties: Dict[str, Any]

    def to_cypher_create(self) -> tuple[str, Dict[str, Any]]:
        """生成 Cypher CREATE 查询"""
        # 转换属性值为 Cypher 兼容格式
        props = {}
        for k, v in self.properties.items():
            if isinstance(v, (list, dict)):
                import json

                props[k] = json.dumps(v)
            else:
                props[k] = v

        query = f"""
        MATCH (from) WHERE from.id = $from_id
        MATCH (to) WHERE to.id = $to_id
        MERGE (from)-[r:{self.type.value}]->(to)
        SET r += $props
        RETURN r
        """
        params = {"from_id": self.from_id, "to_id": self.to_id, "props": props}
        return query, params


@dataclass
class MappingResult:
    """映射结果"""

    nodes: List[GraphNode]
    edges: List[GraphEdge]
    stats: Dict[str, int]
