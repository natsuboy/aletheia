"""
符号过滤器系统
"""

from __future__ import annotations

import fnmatch
import re
from abc import ABC, abstractmethod
from typing import Optional, Sequence

from src.scip_parser.core.types import Document, Index, SymbolInformation, SymbolKind, SymbolRole


class SymbolFilter(ABC):
    """符号过滤器基类"""

    @abstractmethod
    def match(
        self,
        symbol: SymbolInformation,
        document: Optional[Document] = None,
        index: Optional[Index] = None,
    ) -> bool:
        """检查符号是否匹配"""
        pass


class PatternFilter(SymbolFilter):
    """模式过滤器"""

    def __init__(self, pattern: str, use_regex: bool = False):
        self.pattern = pattern
        self.use_regex = use_regex
        if use_regex:
            self.regex = re.compile(pattern)

    def match(
        self,
        symbol: SymbolInformation,
        document: Optional[Document] = None,
        index: Optional[Index] = None,
    ) -> bool:
        name = symbol.display_name
        if self.use_regex:
            return bool(self.regex.search(name))
        return fnmatch.fnmatch(name, self.pattern)


class DocumentFilter(SymbolFilter):
    """文档过滤器"""

    def __init__(self, pattern: str):
        self.pattern = pattern

    def match(
        self,
        symbol: SymbolInformation,
        document: Optional[Document] = None,
        index: Optional[Index] = None,
    ) -> bool:
        if not document:
            return False
        return fnmatch.fnmatch(document.relative_path, self.pattern)


class RoleFilter(SymbolFilter):
    """角色过滤器"""

    def __init__(self, role: SymbolRole):
        self.role = role

    def match(
        self,
        symbol: SymbolInformation,
        document: Optional[Document] = None,
        index: Optional[Index] = None,
    ) -> bool:
        if not index:
            return False

        # 查找定义出现位置
        defn = index.find_definition(symbol.symbol)
        if not defn:
            return False

        return bool(defn.symbol_roles & self.role)


class KindFilter(SymbolFilter):
    """符号类型过滤器"""

    def __init__(self, kind: SymbolKind):
        self.kind = kind

    def match(
        self,
        symbol: SymbolInformation,
        document: Optional[Document] = None,
        index: Optional[Index] = None,
    ) -> bool:
        return symbol.kind == self.kind


class NameFilter(SymbolFilter):
    """符号名称过滤器"""

    def __init__(self, name: str, exact: bool = True):
        self.name = name
        self.exact = exact

    def match(
        self,
        symbol: SymbolInformation,
        document: Optional[Document] = None,
        index: Optional[Index] = None,
    ) -> bool:
        if self.exact:
            return symbol.display_name == self.name
        return self.name in symbol.display_name


class LanguageFilter(SymbolFilter):
    """编程语言过滤器"""

    def __init__(self, language: str):
        self.language = language.lower()

    def match(
        self,
        symbol: SymbolInformation,
        document: Optional[Document] = None,
        index: Optional[Index] = None,
    ) -> bool:
        if not document:
            return False
        return document.language.lower() == self.language


class DocumentationFilter(SymbolFilter):
    """文档过滤器"""

    def __init__(self, has_doc: bool = True):
        self.has_doc = has_doc

    def match(
        self,
        symbol: SymbolInformation,
        document: Optional[Document] = None,
        index: Optional[Index] = None,
    ) -> bool:
        has_documentation = bool(symbol.documentation and len(symbol.documentation) > 0)
        return has_documentation == self.has_doc


class OccurrenceCountFilter(SymbolFilter):
    """引用次数过滤器"""

    def __init__(self, min_count: Optional[int] = None, max_count: Optional[int] = None):
        self.min_count = min_count
        self.max_count = max_count

    def match(
        self,
        symbol: SymbolInformation,
        document: Optional[Document] = None,
        index: Optional[Index] = None,
    ) -> bool:
        if not index:
            return False

        occurrences = index.get_symbol_occurrences(symbol.symbol)
        count = len(occurrences)

        if self.min_count is not None and count < self.min_count:
            return False
        if self.max_count is not None and count > self.max_count:
            return False
        return True


class CompositeFilter(SymbolFilter):
    """组合过滤器基类"""

    def __init__(self, filters: Sequence[SymbolFilter]):
        self.filters = filters

    @abstractmethod
    def match(
        self,
        symbol: SymbolInformation,
        document: Optional[Document] = None,
        index: Optional[Index] = None,
    ) -> bool:
        pass


class AndFilter(CompositeFilter):
    """AND 组合过滤器"""

    def match(
        self,
        symbol: SymbolInformation,
        document: Optional[Document] = None,
        index: Optional[Index] = None,
    ) -> bool:
        return all(f.match(symbol, document, index) for f in self.filters)


class OrFilter(CompositeFilter):
    """OR 组合过滤器"""

    def match(
        self,
        symbol: SymbolInformation,
        document: Optional[Document] = None,
        index: Optional[Index] = None,
    ) -> bool:
        return any(f.match(symbol, document, index) for f in self.filters)


class NotFilter(SymbolFilter):
    """NOT 过滤器"""

    def __init__(self, filter: SymbolFilter):
        self.filter = filter

    def match(
        self,
        symbol: SymbolInformation,
        document: Optional[Document] = None,
        index: Optional[Index] = None,
    ) -> bool:
        return not self.filter.match(symbol, document, index)


class CustomFilter(SymbolFilter):
    """自定义过滤器"""

    def __init__(self, predicate):
        self.predicate = predicate

    def match(
        self,
        symbol: SymbolInformation,
        document: Optional[Document] = None,
        index: Optional[Index] = None,
    ) -> bool:
        return self.predicate(symbol, document, index)
