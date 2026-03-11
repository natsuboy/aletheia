"""
语言适配器协议
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.scip_parser.core.types import SymbolInformation


@runtime_checkable
class LanguageAdapter(Protocol):
    """语言适配器协议

    用于从特定语言的源代码中提取额外信息。
    """

    def enrich(self, symbol: SymbolInformation, source_code: str) -> SymbolInformation:
        """丰富符号信息

        Args:
            symbol: 原始符号信息
            source_code: 源代码内容

        Returns:
            丰富后的符号信息（可能是新的对象）
        """
        ...
