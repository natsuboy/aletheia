"""
依赖关系图构建器
"""

from __future__ import annotations

from typing import Any

import networkx as nx

from src.scip_parser.core.types import Index


class DependencyGraphBuilder:
    """依赖关系图构建器"""

    def __init__(self, index: Index):
        self.index = index
        self.graph: nx.DiGraph = nx.DiGraph()

    def build(self) -> nx.DiGraph:
        """构建依赖图 (基于文件/文档)

        Returns:
            NetworkX 有向图，节点为文件路径，边表示导入/依赖关系
        """
        self.graph = nx.DiGraph()

        # 1. Map symbols to defining documents
        symbol_to_doc: dict[str, str] = {}
        for doc in self.index.documents:
            self.graph.add_node(doc.relative_path)
            # Use doc.symbols (definitions)
            for sym in doc.symbols.keys():
                symbol_to_doc[sym] = doc.relative_path

        # 2. Find imports and add edges
        for doc in self.index.documents:
            for occ in doc.occurrences:
                if occ.is_import:
                    target_path = symbol_to_doc.get(occ.symbol)
                    if target_path and target_path != doc.relative_path:
                        self.graph.add_edge(doc.relative_path, target_path)

        return self.graph

    def get_dependencies(self, file_path: str, reverse: bool = False) -> list[str]:
        """获取依赖

        Args:
            file_path: 文件路径
            reverse: 是否反向(获取依赖于该文件的文件)

        Returns:
            依赖文件列表
        """
        if file_path not in self.graph:
            return []

        if reverse:
            return list(self.graph.predecessors(file_path))
        else:
            return list(self.graph.successors(file_path))

    def get_dependents(self, file_path: str) -> list[str]:
        """获取依赖于该文件的文件 (反向依赖)

        Args:
            file_path: 文件路径

        Returns:
            依赖于该文件的文件列表
        """
        return self.get_dependencies(file_path, reverse=True)

    def analyze_layers(self) -> list[list[str]]:
        """分析模块层级 (分层分析)

        将模块分层, Layer 0 为基础模块 (不依赖其他模块)。

        Returns:
            层级列表，每个元素是该层的模块路径列表
        """
        graph_copy = self.graph.copy()
        layers = []

        while graph_copy.nodes():
            layer = [node for node in graph_copy.nodes() if graph_copy.out_degree(node) == 0]
            if not layer:
                layers.append(list(graph_copy.nodes()))
                break
            layers.append(layer)
            graph_copy.remove_nodes_from(layer)

        return layers

    def find_cycles(self) -> list[list[str]]:
        """查找循环依赖

        Returns:
            循环依赖列表(每个循环是一个文件路径列表)
        """
        return list(nx.simple_cycles(self.graph))

    def compute_stability_metrics(self) -> dict[str, dict[str, Any]]:
        """计算稳定性指标

        Returns:
            指标字典
        """
        metrics = {}
        for node in self.graph.nodes():
            ca = self.graph.in_degree(node)  # Afferent coupling (incoming)
            ce = self.graph.out_degree(node)  # Efferent coupling (outgoing)

            instability = 0.0
            if ca + ce > 0:
                instability = float(ce) / float(ca + ce)

            metrics[node] = {
                "ca": ca,
                "ce": ce,
                "instability": instability,
            }
        return metrics
