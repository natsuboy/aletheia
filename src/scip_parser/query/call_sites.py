"""
Call site location utilities for SCIP indices.

Provides functionality to find where a caller symbol invokes a callee symbol.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.scip_parser.core.types import Index, Occurrence


@dataclass
class CallSite:
    """调用位置信息。

    Attributes:
        document_path: 包含调用的文档相对路径
        occurrence: 表示被调用者引用的 Occurrence 对象
        line_number: 调用的行号（0-based，来自 occurrence.get_start_line()）
    """

    document_path: str
    occurrence: Occurrence
    line_number: int


class CallSiteLocator:
    """在 SCIP 索引数据中定位调用位置。

    此类查找调用者符号调用被调用者符号的具体位置。
    """

    def __init__(self, index: Index):
        """使用 SCIP 索引初始化。

        Args:
            index: 已构建索引的 SCIP Index 对象
        """
        self.index = index

    def find_call_site(self, caller: str, callee: str) -> CallSite | None:
        """查找调用者调用被调用者的调用位置。

        算法：
        1. 查找调用者定义所在的文档
        2. 在该文档中查找被调用者的引用
        3. 返回找到的第一个引用（表示调用位置）

        Args:
            caller: 调用函数/方法的符号字符串
            callee: 被调用函数/方法的符号字符串

        Returns:
            如果找到则返回 CallSite 对象，否则返回 None

        Example:
            >>> locator = CallSiteLocator(index)
            >>> site = locator.find_call_site("main.foo().", "utils.bar().")
            >>> if site:
            ...     print(f"Call at {site.document_path}:{site.line_number}")
        """
        # 查找调用者定义所在的文档
        caller_doc = self.index.get_document_by_symbol(caller)
        if not caller_doc:
            return None

        # 在调用者的文档中查找被调用者的引用
        for occ in caller_doc.occurrences:
            if occ.symbol == callee and occ.is_reference:
                return CallSite(
                    document_path=caller_doc.relative_path,
                    occurrence=occ,
                    line_number=occ.get_start_line(),
                )

        return None

    def find_all_call_sites(self, caller: str, callee: str) -> list[CallSite]:
        """查找调用者调用被调用者的所有调用位置。

        与 find_call_site 返回第一个匹配不同，此方法返回所有出现
        （对于多次调用同一被调用者的函数很有用）。

        Args:
            caller: 调用函数/方法的符号字符串
            callee: 被调用函数/方法的符号字符串

        Returns:
            CallSite 对象列表（可能为空）
        """
        caller_doc = self.index.get_document_by_symbol(caller)
        if not caller_doc:
            return []

        call_sites = []
        for occ in caller_doc.occurrences:
            if occ.symbol == callee and occ.is_reference:
                call_sites.append(
                    CallSite(
                        document_path=caller_doc.relative_path,
                        occurrence=occ,
                        line_number=occ.get_start_line(),
                    )
                )

        return call_sites

    def find_call_sites_in_range(
        self, caller: str, callee: str, start_line: int, end_line: int
    ) -> list[CallSite]:
        """查找特定行范围内的调用位置。

        用于查找特定作用域内的调用（例如，在调用者的函数体内）。

        Args:
            caller: 调用函数/方法的符号字符串
            callee: 被调用函数/方法的符号字符串
            start_line: 行范围起始（0-based，包含）
            end_line: 行范围结束（0-based，包含）

        Returns:
            范围内的 CallSite 对象列表
        """
        all_sites = self.find_all_call_sites(caller, callee)
        return [
            site
            for site in all_sites
            if start_line <= site.line_number <= end_line
        ]


def find_call_site(index: Index, caller: str, callee: str) -> CallSite | None:
    """便捷函数，无需创建定位器即可查找调用位置。

    Args:
        index: SCIP Index 对象
        caller: 调用函数/方法的符号字符串
        callee: 被调用函数/方法的符号字符串

    Returns:
        如果找到则返回 CallSite 对象，否则返回 None
    """
    locator = CallSiteLocator(index)
    return locator.find_call_site(caller, callee)
