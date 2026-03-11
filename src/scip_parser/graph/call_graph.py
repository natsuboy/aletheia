"""
调用图构建器
"""

from __future__ import annotations

from typing import Any

import networkx as nx

from src.scip_parser.core.types import Index


class CallGraphBuilder:
    """调用图构建器"""

    def __init__(self, index: Index):
        self.index = index
        self.graph: nx.DiGraph = nx.DiGraph()

    def build(self) -> nx.DiGraph:
        """构建调用图

        Returns:
            NetworkX 有向图，节点为符号字符串，边表示调用关系
        """
        # Ensure graph is clear if rebuilding? Or init new.
        self.graph = nx.DiGraph()

        for doc in self.index.documents:
            # Sort occurrences by start position
            occurrences = sorted(
                doc.occurrences, key=lambda o: (o.get_start_line(), o.get_start_char())
            )

            # Stack of (symbol, end_line, end_char)
            scope_stack: list[tuple[str, int, int]] = []

            for occ in occurrences:
                # Check if we exited any scopes
                while scope_stack:
                    top_sym, top_end_line, top_end_char = scope_stack[-1]
                    # Check if current occ starts AFTER the scope ends
                    # SCIP ranges: start is inclusive, end is exclusive usually?
                    # Types.py says "end_line, end_char".
                    # If occ starts AT end position, it is outside if end is exclusive.
                    # Assuming standard behavior: start >= end means outside.

                    if occ.get_start_line() > top_end_line or (
                        occ.get_start_line() == top_end_line
                        and occ.get_start_char() >= top_end_char
                    ):
                        scope_stack.pop()
                    else:
                        break

                if occ.is_definition:
                    # 使用 enclosing_range 的实际函数体范围（而非标识符 span）
                    # enclosing_range 格式：[start_line, start_char, end_line, end_char]
                    if occ.has_enclosing_range():
                        end_line = occ.enclosing_range[2]
                        end_char = occ.enclosing_range[3]
                    else:
                        end_line = occ.get_end_line()
                        end_char = occ.get_end_char()
                    scope_stack.append((occ.symbol, end_line, end_char))
                    self.graph.add_node(occ.symbol)

                elif occ.is_reference:
                    if scope_stack:
                        caller = scope_stack[-1][0]
                        callee = occ.symbol
                        self.graph.add_edge(caller, callee)

        return self.graph

    def get_callers(self, symbol: str) -> list[str]:
        """获取调用者

        Args:
            symbol: 符号

        Returns:
            调用者列表
        """
        if symbol not in self.graph:
            return []
        return list(self.graph.predecessors(symbol))

    def get_callees(self, symbol: str) -> list[str]:
        """获取被调用者

        Args:
            symbol: 符号

        Returns:
            被调用者列表
        """
        if symbol not in self.graph:
            return []
        return list(self.graph.successors(symbol))

    def get_call_path(self, from_symbol: str, to_symbol: str) -> list[str] | None:
        """获取调用路径

        Args:
            from_symbol: 起始符号
            to_symbol: 目标符号

        Returns:
            调用路径列表
        """
        try:
            return nx.shortest_path(self.graph, from_symbol, to_symbol)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    def analyze_complexity(self) -> dict[str, dict[str, Any]]:
        """分析复杂度

        Returns:
            复杂度指标字典
        """
        metrics = {}
        for node in self.graph.nodes():
            metrics[node] = {
                "in_degree": self.graph.in_degree(node),
                "out_degree": self.graph.out_degree(node),
            }
        return metrics

    def get_recursive_calls(self) -> list[list[str]]:
        """获取递归调用

        Returns:
            递归调用循环列表 (每个循环是一个符号列表)
        """
        return list(nx.simple_cycles(self.graph))

    def visualize(self, output_path: str):
        """可视化调用图

        Args:
            output_path: 输出文件路径 (支持 .dot)
        """
        if output_path.endswith(".dot"):
            self._write_dot(output_path)
        else:
            try:
                import matplotlib.pyplot as plt

                plt.figure(figsize=(12, 12))
                nx.draw(self.graph, with_labels=True, node_size=1000, font_size=8)
                plt.savefig(output_path)
                plt.close()
            except ImportError:
                self._write_dot(output_path + ".dot")

    def _write_dot(self, path: str):
        """写入 DOT 文件"""
        with open(path, "w", encoding="utf-8") as f:
            f.write("digraph G {\n")
            f.write('  rankdir="LR";\n')
            for node in self.graph.nodes():
                f.write(f'  "{node}" [label="{node.split()[-1]}"];\n')
            for u, v in self.graph.edges():
                f.write(f'  "{u}" -> "{v}";\n')
            f.write("}\n")
