"""
SCIP Parser - 高性能 SCIP 文件解析工具库

这个库提供了完整的 SCIP (Source Code Intelligence Protocol) 文件解析功能,
包括符号查询、关系图构建等高级功能。
"""

from src.scip_parser.core.parser import SCIPParser
from src.scip_parser.core.types import (
    Document,
    Index,
    Occurrence,
    PositionEncoding,
    SymbolInformation,
    SymbolKind,
    SymbolRole,
    SyntaxKind,
    TextEncoding,
)
from src.scip_parser.query.api import QueryAPI
from src.scip_parser.utils import (
    extract_clean_documentation,
    extract_signature,
    extract_signature_from_any,
)
from src.scip_parser.query import (
    CallSiteLocator,
    CallSite,
    find_call_site,
)

__version__ = "0.1.0"
__all__ = [
    "SCIPParser",
    "Index",
    "Document",
    "Occurrence",
    "SymbolInformation",
    "SymbolRole",
    "SyntaxKind",
    "PositionEncoding",
    "TextEncoding",
    "SymbolKind",
    "QueryAPI",
    # Utils
    "extract_clean_documentation",
    "extract_signature",
    "extract_signature_from_any",
    # Query
    "CallSiteLocator",
    "CallSite",
    "find_call_site",
]
