"""
SCIP 查询 API
提供流畅的接口用于查询符号和关系。
"""

from __future__ import annotations

from typing import Any, Optional

from src.scip_parser.core.types import Index, SymbolInformation, SymbolKind, SymbolRole
from src.scip_parser.query.filters import (
    AndFilter,
    CustomFilter,
    DocumentationFilter,
    DocumentFilter,
    KindFilter,
    LanguageFilter,
    NameFilter,
    PatternFilter,
    RoleFilter,
    SymbolFilter,
)
from src.scip_parser.utils.logging_config import get_logger

logger = get_logger(__name__)


class QueryAPI:
    """流畅查询 API"""

    def __init__(self, index: Index):
        self.index = index
        self._filters: list[SymbolFilter] = []

    def execute(self) -> list[SymbolInformation]:
        """执行查询"""
        logger.debug(f"开始执行查询,过滤器数量: {len(self._filters)}")

        # 检查是否有名为 NameFilter 且 exact=True 的过滤器
        name_filter: Optional[NameFilter] = None
        for f in self._filters:
            if isinstance(f, NameFilter) and f.exact:
                name_filter = f
                break

        filtered_results = []
        combined_filter = AndFilter(self._filters)

        # 始终遍历文档以确保正确处理文档相关的过滤器 (如 DocumentFilter, LanguageFilter)
        # 这是为了保持与 SCIP 符号定义位置的语义一致性
        for doc in self.index.documents:
            if name_filter:
                # 优化: 如果有精确名称过滤器,只检查该文档中是否有该名称的符号
                # 在大多数文档中,这会非常快 (dict 查找)
                for sym_info in doc.symbols.values():
                    if sym_info.display_name == name_filter.name:
                        if combined_filter.match(sym_info, document=doc, index=self.index):
                            filtered_results.append(sym_info)
            else:
                # 全量遍历该文档的符号
                for sym_info in doc.symbols.values():
                    if combined_filter.match(sym_info, document=doc, index=self.index):
                        filtered_results.append(sym_info)

        logger.debug(f"查询执行完成: 返回 {len(filtered_results)} 个结果")
        return filtered_results

    def count(self) -> int:
        """返回结果数量"""
        return len(self.execute())

    def first(self) -> Optional[SymbolInformation]:
        """返回第一个结果"""
        res = self.execute()
        return res[0] if res else None

    def exists(self) -> bool:
        """是否存在"""
        combined_filter = AndFilter(self._filters)
        for doc in self.index.documents:
            for sym_info in doc.symbols.values():
                if combined_filter.match(sym_info, document=doc, index=self.index):
                    return True
        return False

    def by_kind(self, kind: SymbolKind) -> "QueryAPI":
        """按符号类型过滤

        Args:
            kind: 符号类型

        Returns:
            QueryAPI 实例，支持链式调用
        """
        self._filters.append(KindFilter(kind))
        return self

    def by_language(self, language: str) -> "QueryAPI":
        """按编程语言过滤

        Args:
            language: 编程语言名称

        Returns:
            QueryAPI 实例，支持链式调用
        """
        self._filters.append(LanguageFilter(language))
        return self

    def by_name(self, name: str, exact: bool = True) -> "QueryAPI":
        """按名称过滤

        Args:
            name: 符号名称
            exact: 是否精确匹配

        Returns:
            QueryAPI 实例，支持链式调用
        """
        self._filters.append(NameFilter(name, exact=exact))
        return self

    def by_pattern(self, pattern: str, use_regex: bool = False) -> "QueryAPI":
        """按模式过滤

        Args:
            pattern: 匹配模式（支持通配符或正则表达式）
            use_regex: 是否使用正则表达式

        Returns:
            QueryAPI 实例，支持链式调用
        """
        self._filters.append(PatternFilter(pattern, use_regex=use_regex))
        return self

    def by_document(self, document_path: str | list[str]) -> "QueryAPI":
        """按文档路径过滤

        Args:
            document_path: 文档路径或路径列表

        Returns:
            QueryAPI 实例，支持链式调用
        """
        if isinstance(document_path, str):
            self._filters.append(DocumentFilter(document_path))
        else:
            # 多个路径使用 OrFilter 组合
            from src.scip_parser.query.filters import OrFilter

            filters = [DocumentFilter(path) for path in document_path]
            self._filters.append(OrFilter(filters))
        return self

    def has_documentation(self) -> "QueryAPI":
        """过滤有文档的符号

        Returns:
            QueryAPI 实例，支持链式调用
        """
        self._filters.append(DocumentationFilter(has_doc=True))
        return self

    def is_exported(self) -> "QueryAPI":
        """过滤导出的符号（有 Definition 角色的符号）

        Returns:
            QueryAPI 实例，支持链式调用
        """
        self._filters.append(RoleFilter(SymbolRole.Definition))
        return self

    def with_role(self, role: SymbolRole) -> "QueryAPI":
        """按角色过滤

        Args:
            role: 符号角色

        Returns:
            QueryAPI 实例，支持链式调用
        """
        self._filters.append(RoleFilter(role))
        return self

    def custom_filter(self, predicate) -> "QueryAPI":
        """使用自定义谓词过滤

        Args:
            predicate: 自定义过滤函数，接收 (symbol, document, index) 参数

        Returns:
            QueryAPI 实例，支持链式调用
        """
        self._filters.append(CustomFilter(predicate))
        return self

    def find_references(self, symbol: str):
        """查找引用"""
        logger.debug(f"QueryAPI: 查找引用 {symbol}")
        return self.index.find_references(symbol)

    def find_implementations(self, symbol: str):
        """查找实现"""
        logger.debug(f"QueryAPI: 查找实现 {symbol}")
        return self.index.find_implementations(symbol)

    def find_hierarchy(self, symbol: str, direction: str = "both") -> list[str]:
        """查找继承层次

        Args:
            symbol: 符号名称
            direction: "up" (父类), "down" (子类), 或 "both" (双向)
        """
        results = set()
        if direction in ("up", "both"):
            results.update(self.index.find_supertypes(symbol))
        if direction in ("down", "both"):
            results.update(self.index.find_subtypes(symbol))
        return list(results)

    def group_by_kind(self) -> dict[SymbolKind, list[SymbolInformation]]:
        """按符号类型分组"""
        results: dict[SymbolKind, list[SymbolInformation]] = {}
        for sym in self.execute():
            if sym.kind not in results:
                results[sym.kind] = []
            results[sym.kind].append(sym)
        return results

    def group_by_document(self) -> dict[str, list[SymbolInformation]]:
        """按文档分组"""
        results: dict[str, list[SymbolInformation]] = {}
        combined_filter = AndFilter(self._filters)

        for doc in self.index.documents:
            for sym_info in doc.symbols.values():
                if combined_filter.match(sym_info, document=doc, index=self.index):
                    if doc.relative_path not in results:
                        results[doc.relative_path] = []
                    results[doc.relative_path].append(sym_info)
        return results

    def aggregate_stats(self) -> dict[str, Any]:
        """聚合统计信息"""
        symbols = self.execute()
        from collections import Counter

        return {
            "count": len(symbols),
            "kind_distribution": Counter(s.kind.name for s in symbols),
        }
