"""
Documentation processing utilities for SCIP symbol information.

Provides functions to clean and merge documentation strings from SCIP data.
"""

from __future__ import annotations
import re


def merge_documentation(documentation_list: tuple[str, ...] | list[str]) -> str:
    """合并多个文档字符串为单一文本。

    Args:
        documentation_list: 文档字符串列表或元组

    Returns:
        合并后的文档字符串
    """
    if not documentation_list:
        return ""
    return "\n".join(documentation_list)


def remove_code_blocks(doc_text: str) -> str:
    """从文档中移除 markdown 代码块。

    根据 SCIP 规范，documentation 可能包含:
    1. 纯文本文档注释
    2. markdown 代码块 + 文本文档
    3. 只有 markdown 代码块(签名，无实际文档)

    此函数移除所有代码块 (```language\\n...\\n```) 并只保留描述性文本。

    Args:
        doc_text: 可能包含 markdown 代码块的文档文本

    Returns:
        移除代码块后的文档

    Example:
        >>> doc = "\\n```python\\ndef foo(): pass\\n```\\n\\nThis is a function."
        >>> remove_code_blocks(doc)
        'This is a function.'
    """
    # 匹配 ```language\n...\n``` 格式的代码块
    # 使用 DOTALL 标志以匹配跨行内容
    doc = re.sub(r'```[a-zA-Z]*\n.*?\n```', '', doc_text, flags=re.DOTALL)
    return doc.strip()


def clean_whitespace(doc_text: str) -> str:
    """清理文档中的多余空白和空行。

    Args:
        doc_text: 文档文本

    Returns:
        清理后的文档文本
    """
    # 移除多个连续的空行
    doc = re.sub(r'\n\s*\n\s*\n+', '\n\n', doc_text)
    return doc.strip()


def extract_clean_documentation(documentation_list: tuple[str, ...] | list[str]) -> str:
    """提取干净的文档，不包含代码块。

    这是主要的 API 函数，组合了所有清理操作。

    Args:
        documentation_list: 来自 SCIP 的文档字符串列表或元组

    Returns:
        不包含代码块的干净文档文本

    Example:
        >>> docs = ["```python\\ndef foo():\\n    pass\\n```", "This is a function."]
        >>> extract_clean_documentation(docs)
        'This is a function.'
    """
    if not documentation_list:
        return ""

    merged = merge_documentation(documentation_list)
    without_code = remove_code_blocks(merged)
    cleaned = clean_whitespace(without_code)

    return cleaned
