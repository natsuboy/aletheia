"""
符号搜索器
"""

from __future__ import annotations

import difflib

from src.scip_parser.core.types import Index, SymbolInformation


class SymbolSearcher:
    """符号搜索器"""

    def __init__(self, index: Index):
        self.index = index

    def search(self, query: str) -> list[SymbolInformation]:
        """搜索符号 (包含匹配)

        Args:
            query: 查询字符串

        Returns:
            匹配的符号列表
        """
        return self.index.search_symbols(query)

    def fuzzy_search(
        self, query: str, limit: int = 10, cutoff: float = 0.6
    ) -> list[SymbolInformation]:
        """模糊搜索 (基于相似度)

        Args:
            query: 查询字符串
            limit: 最大结果数
            cutoff: 相似度阈值 (0-1)

        Returns:
            匹配的符号列表
        """
        name_map: dict[str, list[SymbolInformation]] = {}
        for doc in self.index.documents:
            for sym in doc.symbols.values():
                if sym.display_name not in name_map:
                    name_map[sym.display_name] = []
                name_map[sym.display_name].append(sym)

        candidates = list(name_map.keys())
        matches = difflib.get_close_matches(query, candidates, n=limit, cutoff=cutoff)

        results = []
        for match in matches:
            results.extend(name_map[match])

        return results

    def autocomplete(self, prefix: str, limit: int = 10) -> list[SymbolInformation]:
        """自动完成 (前缀匹配)

        Args:
            prefix: 前缀
            limit: 最大结果数

        Returns:
            匹配的符号列表
        """
        prefix_lower = prefix.lower()
        results = []

        for doc in self.index.documents:
            for sym in doc.symbols.values():
                if sym.display_name.lower().startswith(prefix_lower):
                    results.append(sym)

        # Sort by display name
        results.sort(key=lambda s: s.display_name)

        return results[:limit]
