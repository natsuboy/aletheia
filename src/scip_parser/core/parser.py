"""
SCIP 文件解析器

这个模块提供了 SCIP 文件的解析功能,支持解析 .scip 和 .scip.gz 格式的文件。
"""

from __future__ import annotations

import gzip
from io import BytesIO
from typing import TYPE_CHECKING, BinaryIO

from src.scip_parser.core.types import (
    Document,
    Index,
    Metadata,
    Occurrence,
    PositionEncoding,
    Relationship,
    SymbolInformation,
    SymbolKind,
    SyntaxKind,
    TextEncoding,
    ToolInfo,
)
from src.scip_parser.proto import scip_pb2
from src.scip_parser.utils.logging_config import get_logger

if TYPE_CHECKING:
    import io

logger = get_logger(__name__)


class SCIPParser:
    """SCIP 文件解析器

    负责读取 SCIP 文件并将其转换为 Python 对象。
    """

    enable_indexing: bool

    def __init__(self, enable_indexing: bool = True):
        """
        Args:
            enable_indexing: 是否构建内部索引以加速查询(默认 True)
        """
        self.enable_indexing = enable_indexing

    def parse_file(self, path: str) -> Index:
        """解析 SCIP 文件

        Args:
            path: SCIP 文件路径(可以是 .scip 或 .scip.gz)

        Returns:
            Index 对象

        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 文件格式错误
        """
        logger.debug(f"开始解析 SCIP 文件: {path}")
        # 检测是否为 gzip 压缩
        if path.endswith(".gz"):
            logger.debug("检测到 gzip 压缩文件")
            with gzip.open(path, "rb") as f:
                result = self._parse_stream(f)
        else:
            logger.debug("检测到未压缩文件")
            with open(path, "rb") as f:
                result = self._parse_stream(f)
        logger.debug(f"SCIP 文件解析完成: {path}")
        return result

    def parse_bytes(self, data: bytes) -> Index:
        """解析字节流

        Args:
            data: SCIP 文件的字节内容

        Returns:
            Index 对象
        """
        return self._parse_stream(BytesIO(data))

    def _parse_stream(self, stream: BinaryIO | io.BufferedIOBase) -> Index:
        """从流解析 SCIP 索引

        Args:
            stream: 二进制输入流

        Returns:
            Index 对象

        Raises:
            ValueError: 如果流内容不是有效的 SCIP 索引
        """
        logger.debug("开始解析 Protocol Buffer 消息")
        # 解析 Protocol Buffer 消息
        pb_index = scip_pb2.Index()
        try:
            data = stream.read()
            logger.debug(f"读取了 {len(data)} 字节的二进制数据")
            _ = pb_index.ParseFromString(data)
            logger.debug(f"Protocol Buffer 解析成功,包含 {len(pb_index.documents)} 个文档")
        except Exception as e:
            logger.error(f"Protocol Buffer 解析失败: {e}")
            raise ValueError(f"Failed to parse SCIP index: {e}")

        # 转换为 Python 数据模型
        logger.debug("开始转换为 Python 数据模型")
        index = self._convert_pb_to_index(pb_index)

        # 构建内部索引
        if self.enable_indexing:
            logger.debug("开始构建内部索引")
            index.build_indexes()
        else:
            logger.debug("索引构建已禁用")

        return index

    def _convert_pb_to_index(self, pb_index: scip_pb2.Index) -> Index:
        """将 protobuf 消息转换为 Python 对象

        Args:
            pb_index: Protocol Buffer Index 消息

        Returns:
            Python Index 对象
        """
        logger.debug("转换元数据")
        # 转换元数据
        metadata = self._convert_metadata(pb_index.metadata)
        logger.debug(f"元数据: version={metadata.version}, project_root={metadata.project_root}")

        # 转换文档列表
        logger.debug(f"开始转换 {len(pb_index.documents)} 个文档")
        documents = [self._convert_document(pb_doc) for pb_doc in pb_index.documents]

        # 转换外部符号
        logger.debug(f"开始转换 {len(pb_index.external_symbols)} 个外部符号")
        external_symbols = [
            self._convert_symbol_info(pb_sym) for pb_sym in pb_index.external_symbols
        ]

        logger.debug("数据模型转换完成")
        return Index(
            metadata=metadata,
            documents=tuple(documents),
            external_symbols=tuple(external_symbols),
        )

    def _convert_metadata(self, pb_metadata: scip_pb2.Metadata) -> Metadata:
        """转换元数据

        Args:
            pb_metadata: Protocol Buffer Metadata 消息

        Returns:
            Python Metadata 对象
        """
        tool_info = ToolInfo(
            name=pb_metadata.tool_info.name,
            version=pb_metadata.tool_info.version,
            arguments=tuple(pb_metadata.tool_info.arguments),
        )

        return Metadata(
            version=pb_metadata.version,
            tool_info=tool_info,
            project_root=pb_metadata.project_root,
            text_document_encoding=TextEncoding(pb_metadata.text_document_encoding),
        )

    def _convert_document(self, pb_document: scip_pb2.Document) -> Document:
        """转换文档

        Args:
            pb_document: Protocol Buffer Document 消息

        Returns:
            Python Document 对象
        """
        logger.debug(
            f"转换文档: {pb_document.relative_path} ({pb_document.language}), "
            f"包含 {len(pb_document.occurrences)} 个出现位置, {len(pb_document.symbols)} 个符号"
        )
        # 转换出现位置列表
        occurrences = [self._convert_occurrence(pb_occ) for pb_occ in pb_document.occurrences]

        # 转换符号信息字典
        symbols = {
            pb_sym.symbol: self._convert_symbol_info(pb_sym) for pb_sym in pb_document.symbols
        }

        return Document(
            relative_path=pb_document.relative_path,
            language=pb_document.language,
            occurrences=tuple(occurrences),
            symbols=symbols,
            text=pb_document.text,
            position_encoding=PositionEncoding(pb_document.position_encoding),
        )

    def _convert_occurrence(self, pb_occurrence: scip_pb2.Occurrence) -> Occurrence:
        """转换出现位置

        Args:
            pb_occurrence: Protocol Buffer Occurrence 消息

        Returns:
            Python Occurrence 对象
        """
        # 转换范围
        range_values = list(pb_occurrence.range)

        # 转换语法类型
        syntax_kind = None
        if pb_occurrence.syntax_kind != 0:
            syntax_kind = SyntaxKind(pb_occurrence.syntax_kind)

        # 转换符号角色
        symbol_roles = pb_occurrence.symbol_roles

        return Occurrence(
            range=tuple(range_values),
            symbol=pb_occurrence.symbol,
            symbol_roles=symbol_roles,
            syntax_kind=syntax_kind,
            enclosing_range=tuple(pb_occurrence.enclosing_range),
            override_documentation=tuple(pb_occurrence.override_documentation),
        )

    def _convert_symbol_info(self, pb_sym_info: scip_pb2.SymbolInformation) -> SymbolInformation:
        """转换符号信息

        Args:
            pb_sym_info: Protocol Buffer SymbolInformation 消息

        Returns:
            Python SymbolInformation 对象
        """
        # 转换关系列表
        relationships = [
            Relationship(
                symbol=rel.symbol,
                is_reference=rel.is_reference,
                is_implementation=rel.is_implementation,
                is_type_definition=rel.is_type_definition,
                is_definition=rel.is_definition,
            )
            for rel in pb_sym_info.relationships
        ]

        # 转换 signature_documentation
        signature_documentation = None
        if pb_sym_info.HasField("signature_documentation"):
            signature_documentation = self._convert_document(pb_sym_info.signature_documentation)

        # display_name fallback: 如果未提供且不是本地符号，从符号字符串解析
        display_name = pb_sym_info.display_name
        if not display_name and not pb_sym_info.symbol.startswith("local "):
            from src.scip_parser.utils.symbol import SymbolParser

            inferred_name, _ = SymbolParser.infer_metadata(pb_sym_info.symbol)
            if inferred_name:
                display_name = inferred_name

        # kind fallback: 如果为 Unspecified 且不是本地符号，从符号字符串推断
        kind = SymbolKind(pb_sym_info.kind)
        if kind == SymbolKind.Unspecified and not pb_sym_info.symbol.startswith("local "):
            from src.scip_parser.utils.symbol import SymbolParser

            _, inferred_kind = SymbolParser.infer_metadata(pb_sym_info.symbol)
            if inferred_kind != SymbolKind.Unspecified:
                kind = inferred_kind
                logger.warning(
                    f"SymbolInformation.kind 未指定，从符号推断: '{pb_sym_info.symbol}' -> '{kind.name}'"
                )

        return SymbolInformation(
            symbol=pb_sym_info.symbol,
            kind=kind,
            display_name=display_name,
            documentation=tuple(pb_sym_info.documentation),
            relationships=tuple(relationships),
            enclosing_symbol=pb_sym_info.enclosing_symbol if pb_sym_info.enclosing_symbol else None,
            signature_documentation=signature_documentation,
        )
