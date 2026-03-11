"""
继承关系图构建器
"""

from __future__ import annotations

from typing import Any, Optional, cast

import networkx as nx

from src.scip_parser.core.types import Index


class InheritanceGraphBuilder:
    """继承关系图构建器"""

    def __init__(self, index: Index):
        self.index = index
        self.graph: nx.DiGraph = nx.DiGraph()

    def build(self) -> nx.DiGraph:
        """构建继承图

        Returns:
            NetworkX 有向图，节点为符号，边表示继承关系 (Child -> Parent)
        """
        self.graph = nx.DiGraph()

        for doc in self.index.documents:
            for sym_info in doc.symbols.values():
                self.graph.add_node(sym_info.symbol)

                for rel in sym_info.relationships:
                    if rel.is_implementation:
                        # Edge from Parent (rel.symbol) to Child (sym_info.symbol)
                        # This enables nx.lowest_common_ancestor to work correctly
                        self.graph.add_edge(rel.symbol, sym_info.symbol)
                        self.graph.add_node(rel.symbol)  # Ensure parent exists

        return self.graph

    def get_parents(self, symbol: str) -> list[str]:
        """获取父类/接口

        Args:
            symbol: 子类符号

        Returns:
            父类符号列表
        """
        if symbol not in self.graph:
            return []
        return list(self.graph.predecessors(symbol))

    def get_children(self, symbol: str) -> list[str]:
        """获取子类/实现

        Args:
            symbol: 父类符号

        Returns:
            子类符号列表
        """
        if symbol not in self.graph:
            return []
        return list(self.graph.successors(symbol))

    def find_common_ancestor(self, symbol1: str, symbol2: str) -> Optional[str]:
        """查找最近公共祖先

        Args:
            symbol1: 符号1
            symbol2: 符号2

        Returns:
            公共祖先符号
        """
        if symbol1 not in self.graph or symbol2 not in self.graph:
            return None

        try:
            return cast(str, nx.lowest_common_ancestor(self.graph, symbol1, symbol2))
        except (nx.NetworkXError, nx.NodeNotFound):
            return None

    def get_ancestors(self, symbol: str) -> list[str]:
        """获取所有祖先类/接口

        Args:
            symbol: 符号

        Returns:
            所有祖先符号列表
        """
        if symbol not in self.graph:
            return []
        return list(nx.ancestors(self.graph, symbol))

    def get_descendants(self, symbol: str) -> list[str]:
        """获取所有后代类/实现

        Args:
            symbol: 符号

        Returns:
            所有后代符号列表
        """
        if symbol not in self.graph:
            return []
        return list(nx.descendants(self.graph, symbol))

    def get_method_resolution_order(self, symbol: str) -> list[str]:
        """计算方法解析顺序 (MRO)

        Args:
            symbol: 符号

        Returns:
            MRO 符号列表
        """
        if symbol not in self.graph:
            return []

        mro = []
        visited = set()
        queue = [symbol]
        visited.add(symbol)

        while queue:
            current = queue.pop(0)
            mro.append(current)
            for parent in self.get_parents(current):
                if parent not in visited:
                    visited.add(parent)
                    queue.append(parent)
        return mro

    def find_diamond_inheritance(self) -> list[dict[str, Any]]:
        """查找菱形继承

        菱形继承是指一个类通过多个路径继承同一个基类的情况。
        例如：
            A
           / \\
          B   C
           \\ /
            D

        Returns:
            菱形继承信息列表，每项包含：
            - base: 基类符号
            - paths: 到达基类的不同路径
            - descendant: 涉及的子类符号
        """
        diamonds = []

        # 遍历所有节点，查找有多个父类的节点
        for node in self.graph.nodes():
            parents = self.get_parents(node)

            # 如果节点有多个父类，检查这些父类是否有共同的祖先
            if len(parents) >= 2:
                # 检查所有父类对之间是否有共同祖先
                for i, parent1 in enumerate(parents):
                    for parent2 in parents[i + 1 :]:
                        # 找到 parent1 和 parent2 的共同祖先
                        common_ancestor = self.find_common_ancestor(parent1, parent2)

                        if common_ancestor:
                            # 找到从 common_ancestor 到 node 的所有路径
                            try:
                                paths = list(nx.all_simple_paths(self.graph, common_ancestor, node))

                                if len(paths) >= 2:
                                    diamonds.append(
                                        {
                                            "base": common_ancestor,
                                            "paths": paths,
                                            "descendant": node,
                                        }
                                    )
                            except (nx.NetworkXNoPath, nx.NodeNotFound):
                                pass

        return diamonds

    def analyze_depth(self, symbol: str) -> dict[str, int]:
        """分析继承深度

        Args:
            symbol: 符号

        Returns:
            深度信息字典：
            - direct_depth: 直接继承深度（父类数量）
            - total_depth: 总继承深度（到根节点的最长路径长度）
            - class_count: 祖先类数量
        """
        if symbol not in self.graph:
            return {"direct_depth": 0, "total_depth": 0, "class_count": 0}

        parents = self.get_parents(symbol)
        direct_depth = len(parents)

        # 计算到根节点的最长路径
        total_depth = 0
        if parents:
            max_parent_depth = 0
            for parent in parents:
                try:
                    # 计算从 parent 到根节点的最长路径
                    parent_depth = 0
                    visited = set()
                    current_parents = [parent]

                    while current_parents:
                        next_parents = []
                        for p in current_parents:
                            if p not in visited:
                                visited.add(p)
                                next_parents.extend(self.get_parents(p))
                        if next_parents:
                            parent_depth += 1
                        current_parents = next_parents

                    max_parent_depth = max(max_parent_depth, parent_depth)
                except Exception:
                    pass

            total_depth = max_parent_depth + 1

        # 计算祖先类数量
        ancestors = self.get_ancestors(symbol)
        class_count = len(ancestors)

        return {
            "direct_depth": direct_depth,
            "total_depth": total_depth,
            "class_count": class_count,
        }
