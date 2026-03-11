"""
Signature extraction utilities for SCIP symbol information.

Extracts signatures from signature_documentation or documentation markdown.
"""

from __future__ import annotations
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.scip_parser.core.types import SymbolInformation


def extract_signature_from_signature_documentation(symbol_info: SymbolInformation) -> str:
    """从 signature_documentation 字段提取签名（首选方法）。

    根据 SCIP 规范，signature_documentation.text 是推荐的签名来源。

    Args:
        symbol_info: SymbolInformation 对象

    Returns:
        如果可用则返回签名文本，否则返回空字符串
    """
    if not hasattr(symbol_info, "signature_documentation"):
        return ""

    sig_doc = symbol_info.signature_documentation
    if sig_doc is None:
        return ""

    if not hasattr(sig_doc, "text"):
        return ""

    text = sig_doc.text
    if text:
        return text.strip()

    return ""


def extract_signature_from_markdown(documentation_list: tuple[str, ...] | list[str]) -> str:
    """从文档中的 markdown 代码块提取签名。

    历史上，索引器常常将签名放在 documentation 字段的第一个 markdown 代码块中。
    这是一个回退方法。

    Args:
        documentation_list: 文档字符串列表

    Returns:
        从第一个代码块提取的签名，或空字符串

    Example:
        >>> docs = ["```python\\ndef foo(x: int) -> int:\\n    pass\\n```", "Description"]
        >>> extract_signature_from_markdown(docs)
        'def foo(x: int) -> int:'
    """
    if not documentation_list:
        return ""

    for doc in documentation_list:
        # 检查是否是代码块: ```language\ncode\n```
        if doc.startswith("```"):
            lines = doc.split("\n")
            if len(lines) >= 2:
                # 第二行是签名（跳过 ```language 行）
                signature = lines[1].strip()
                if signature:  # 确保不是空行
                    return signature

    return ""


def extract_signature(symbol_info: SymbolInformation) -> str:
    """从 SymbolInformation 使用最佳可用来源提取签名。

    这是主要的 API 函数。按优先级顺序尝试多个来源：
    1. signature_documentation.text（SCIP 规范推荐）
    2. documentation 中的第一个 markdown 代码块（传统/回退）

    Args:
        symbol_info: SymbolInformation 对象

    Returns:
        提取的签名字符串，如果不可用则返回空字符串

    Example:
        >>> from scip_parser import SCIPParser
        >>> parser = SCIPParser()
        >>> index = parser.parse_file("project.scip")
        >>> symbol_info = index.get_symbol_info("some_symbol")
        >>> signature = extract_signature(symbol_info)
    """
    # 方法 1: 尝试 signature_documentation（首选）
    signature = extract_signature_from_signature_documentation(symbol_info)
    if signature:
        return signature

    # 方法 2: 尝试 documentation markdown 代码块（回退）
    if hasattr(symbol_info, "documentation"):
        signature = extract_signature_from_markdown(symbol_info.documentation)
        if signature:
            return signature

    # 无法提取签名
    return ""


def extract_signature_from_any(data: Any) -> str:
    """从任何数据对象提取签名（SymbolData 或 SymbolInformation）。

    这是一个便捷函数，用于处理包装数据的提取器。

    Args:
        data: SymbolInformation 或具有 symbol_info 属性的包装对象

    Returns:
        提取的签名字符串
    """
    # 检查是否是包装对象（如 SymbolData）
    if hasattr(data, "symbol_info"):
        return extract_signature(data.symbol_info)

    # 假设它直接是 SymbolInformation
    return extract_signature(data)
