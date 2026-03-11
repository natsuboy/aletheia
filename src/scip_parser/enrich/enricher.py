"""
源码补全器
"""

from __future__ import annotations

import os

from src.scip_parser.core.types import SymbolInformation
from src.scip_parser.enrich.adapter import LanguageAdapter
from src.scip_parser.enrich.provider import SourceProvider


class SourceEnricher:
    """源码补全协调器"""

    def __init__(self, provider: SourceProvider):
        self.provider = provider
        self._adapters: dict[str, LanguageAdapter] = {}

    def register_adapter(self, extension: str, adapter: LanguageAdapter):
        """注册语言适配器

        Args:
            extension: 文件扩展名（如 ".go"）
            adapter: 适配器实例
        """
        self._adapters[extension] = adapter

    def enrich_symbol(self, symbol: SymbolInformation, document_path: str) -> SymbolInformation:
        """丰富符号信息

        Args:
            symbol: 原始符号信息
            document_path: 文档相对路径

        Returns:
            丰富后的符号信息
        """
        _, ext = os.path.splitext(document_path)
        adapter = self._adapters.get(ext)
        if not adapter:
            return symbol

        source_code = self.provider.get_content(document_path)
        if source_code is None:
            return symbol

        return adapter.enrich(symbol, source_code)
