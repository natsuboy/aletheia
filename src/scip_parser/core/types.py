"""
SCIP 核心数据类型定义

这个模块定义了 SCIP 协议中所有核心数据结构的 Python 表示。
所有数据类使用 @dataclass(frozen=True) 以确保不可变性,这对于
性能优化和线程安全非常重要。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any, TypedDict

from typing_extensions import override

from src.scip_parser.proto import scip_pb2
from src.scip_parser.utils.logging_config import get_logger

logger = get_logger(__name__)


class SymbolRole(IntEnum):
    """符号角色位掩码

    SCIP 使用位掩码来表示符号在出现位置的角色。一个符号可以同时具有多个角色。
    例如: role & SymbolRole.DEFINITION > 0 表示这是一个定义
    """

    Unspecified = scip_pb2.UnspecifiedSymbolRole
    Definition = scip_pb2.Definition  # 符号定义
    Import = scip_pb2.Import  # 符号导入
    WriteAccess = scip_pb2.WriteAccess  # 写入访问
    ReadAccess = scip_pb2.ReadAccess  # 读取访问
    Generated = scip_pb2.Generated  # 生成的代码
    Test = scip_pb2.Test  # 测试代码
    ForwardDefinition = scip_pb2.ForwardDefinition  # 前向声明


class SyntaxKind(Enum):
    """语法类型枚举

    定义源代码中各种语法元素的类型,用于语法高亮和分类。
    """

    Unspecified = scip_pb2.UnspecifiedSyntaxKind
    Comment = scip_pb2.Comment
    PunctuationDelimiter = scip_pb2.PunctuationDelimiter
    PunctuationBracket = scip_pb2.PunctuationBracket
    Keyword = scip_pb2.Keyword
    IdentifierOperator = scip_pb2.IdentifierOperator
    Identifier = scip_pb2.Identifier
    IdentifierBuiltin = scip_pb2.IdentifierBuiltin
    IdentifierNull = scip_pb2.IdentifierNull
    IdentifierConstant = scip_pb2.IdentifierConstant
    IdentifierMutableGlobal = scip_pb2.IdentifierMutableGlobal
    IdentifierParameter = scip_pb2.IdentifierParameter
    IdentifierLocal = scip_pb2.IdentifierLocal
    IdentifierShadowed = scip_pb2.IdentifierShadowed
    IdentifierNamespace = scip_pb2.IdentifierNamespace
    IdentifierFunction = scip_pb2.IdentifierFunction
    IdentifierFunctionDefinition = scip_pb2.IdentifierFunctionDefinition
    IdentifierMacro = scip_pb2.IdentifierMacro
    IdentifierMacroDefinition = scip_pb2.IdentifierMacroDefinition
    IdentifierType = scip_pb2.IdentifierType
    IdentifierBuiltinType = scip_pb2.IdentifierBuiltinType
    IdentifierAttribute = scip_pb2.IdentifierAttribute
    RegexEscape = scip_pb2.RegexEscape
    RegexRepeated = scip_pb2.RegexRepeated
    RegexWildcard = scip_pb2.RegexWildcard
    RegexDelimiter = scip_pb2.RegexDelimiter
    RegexJoin = scip_pb2.RegexJoin
    StringLiteral = scip_pb2.StringLiteral
    StringLiteralEscape = scip_pb2.StringLiteralEscape
    StringLiteralSpecial = scip_pb2.StringLiteralSpecial
    StringLiteralKey = scip_pb2.StringLiteralKey
    CharacterLiteral = scip_pb2.CharacterLiteral
    NumericLiteral = scip_pb2.NumericLiteral
    BooleanLiteral = scip_pb2.BooleanLiteral
    Tag = scip_pb2.Tag
    TagAttribute = scip_pb2.TagAttribute
    TagDelimiter = scip_pb2.TagDelimiter


class PositionEncoding(Enum):
    """位置编码方式

    定义如何解释 range 中的 character 值。
    """

    Unspecified = scip_pb2.UnspecifiedPositionEncoding
    UTF8CodeUnitOffsetFromLineStart = scip_pb2.UTF8CodeUnitOffsetFromLineStart  # UTF-8 字节偏移
    UTF16CodeUnitOffsetFromLineStart = (
        scip_pb2.UTF16CodeUnitOffsetFromLineStart
    )  # UTF-16 代码单元偏移
    UTF32CodeUnitOffsetFromLineStart = (
        scip_pb2.UTF32CodeUnitOffsetFromLineStart
    )  # UTF-32 代码单元偏移(字符数)


class TextEncoding(Enum):
    """文本编码方式"""

    Unspecified = scip_pb2.UnspecifiedTextEncoding
    UTF8 = scip_pb2.UTF8
    UTF16 = scip_pb2.UTF16


class SymbolKind(Enum):
    """符号类型

    定义符号的具体类型(类、方法、函数等),提供比 Descriptor.Suffix 更细粒度的分类。
    """

    Unspecified = scip_pb2.SymbolInformation.UnspecifiedKind
    Array = scip_pb2.SymbolInformation.Array
    Assertion = scip_pb2.SymbolInformation.Assertion
    AssociatedType = scip_pb2.SymbolInformation.AssociatedType
    Attribute = scip_pb2.SymbolInformation.Attribute
    Axiom = scip_pb2.SymbolInformation.Axiom
    Boolean = scip_pb2.SymbolInformation.Boolean
    Class = scip_pb2.SymbolInformation.Class
    Constant = scip_pb2.SymbolInformation.Constant
    Constructor = scip_pb2.SymbolInformation.Constructor
    DataFamily = scip_pb2.SymbolInformation.DataFamily
    Delegate = scip_pb2.SymbolInformation.Delegate
    Enum = scip_pb2.SymbolInformation.Enum
    EnumMember = scip_pb2.SymbolInformation.EnumMember
    Error = scip_pb2.SymbolInformation.Error
    Event = scip_pb2.SymbolInformation.Event
    Extension = scip_pb2.SymbolInformation.Extension
    Fact = scip_pb2.SymbolInformation.Fact
    Field = scip_pb2.SymbolInformation.Field
    File = scip_pb2.SymbolInformation.File
    Function = scip_pb2.SymbolInformation.Function
    Getter = scip_pb2.SymbolInformation.Getter
    Grammar = scip_pb2.SymbolInformation.Grammar
    Instance = scip_pb2.SymbolInformation.Instance
    Interface = scip_pb2.SymbolInformation.Interface
    Key = scip_pb2.SymbolInformation.Key
    Lang = scip_pb2.SymbolInformation.Lang
    Lemma = scip_pb2.SymbolInformation.Lemma
    Library = scip_pb2.SymbolInformation.Library
    Macro = scip_pb2.SymbolInformation.Macro
    Method = scip_pb2.SymbolInformation.Method
    MethodReceiver = scip_pb2.SymbolInformation.MethodReceiver
    Message = scip_pb2.SymbolInformation.Message
    Mixin = scip_pb2.SymbolInformation.Mixin
    Module = scip_pb2.SymbolInformation.Module
    Namespace = scip_pb2.SymbolInformation.Namespace
    Null = scip_pb2.SymbolInformation.Null
    Number = scip_pb2.SymbolInformation.Number
    Object = scip_pb2.SymbolInformation.Object
    Operator = scip_pb2.SymbolInformation.Operator
    Package = scip_pb2.SymbolInformation.Package
    PackageObject = scip_pb2.SymbolInformation.PackageObject
    Parameter = scip_pb2.SymbolInformation.Parameter
    ParameterLabel = scip_pb2.SymbolInformation.ParameterLabel
    Pattern = scip_pb2.SymbolInformation.Pattern
    Predicate = scip_pb2.SymbolInformation.Predicate
    Property = scip_pb2.SymbolInformation.Property
    Protocol = scip_pb2.SymbolInformation.Protocol
    Quasiquoter = scip_pb2.SymbolInformation.Quasiquoter
    SelfParameter = scip_pb2.SymbolInformation.SelfParameter
    Setter = scip_pb2.SymbolInformation.Setter
    Signature = scip_pb2.SymbolInformation.Signature
    Subscript = scip_pb2.SymbolInformation.Subscript
    String = scip_pb2.SymbolInformation.String
    Struct = scip_pb2.SymbolInformation.Struct
    Tactic = scip_pb2.SymbolInformation.Tactic
    Theorem = scip_pb2.SymbolInformation.Theorem
    ThisParameter = scip_pb2.SymbolInformation.ThisParameter
    Trait = scip_pb2.SymbolInformation.Trait
    Type = scip_pb2.SymbolInformation.Type
    TypeAlias = scip_pb2.SymbolInformation.TypeAlias
    TypeClass = scip_pb2.SymbolInformation.TypeClass
    TypeFamily = scip_pb2.SymbolInformation.TypeFamily
    TypeParameter = scip_pb2.SymbolInformation.TypeParameter
    Union = scip_pb2.SymbolInformation.Union
    Value = scip_pb2.SymbolInformation.Value
    Variable = scip_pb2.SymbolInformation.Variable
    Contract = scip_pb2.SymbolInformation.Contract
    Modifier = scip_pb2.SymbolInformation.Modifier
    AbstractMethod = scip_pb2.SymbolInformation.AbstractMethod
    MethodSpecification = scip_pb2.SymbolInformation.MethodSpecification
    ProtocolMethod = scip_pb2.SymbolInformation.ProtocolMethod
    PureVirtualMethod = scip_pb2.SymbolInformation.PureVirtualMethod
    TraitMethod = scip_pb2.SymbolInformation.TraitMethod
    TypeClassMethod = scip_pb2.SymbolInformation.TypeClassMethod
    Accessor = scip_pb2.SymbolInformation.Accessor
    MethodAlias = scip_pb2.SymbolInformation.MethodAlias
    SingletonClass = scip_pb2.SymbolInformation.SingletonClass
    SingletonMethod = scip_pb2.SymbolInformation.SingletonMethod
    StaticDataMember = scip_pb2.SymbolInformation.StaticDataMember
    StaticEvent = scip_pb2.SymbolInformation.StaticEvent
    StaticField = scip_pb2.SymbolInformation.StaticField
    StaticMethod = scip_pb2.SymbolInformation.StaticMethod
    StaticProperty = scip_pb2.SymbolInformation.StaticProperty
    StaticVariable = scip_pb2.SymbolInformation.StaticVariable
    Concept = scip_pb2.SymbolInformation.Concept


@dataclass(frozen=True)
class Package:
    """包信息

    表示一个包/模块的基本信息。
    """

    manager: str  # 包管理器(如 npm, maven, pip 等)
    name: str  # 包名
    version: str  # 版本号

    @override
    def __str__(self) -> str:
        """格式化为 SCIP 包字符串"""
        return f"{self.manager} {self.name} {self.version}"


@dataclass(frozen=True)
class Descriptor:
    """符号描述符

    描述符用于构建符号的层次结构。
    """

    name: str  # 描述符名称
    disambiguator: str = ""  # 消歧义符(用于重载等场景)
    suffix: int = 0  # Descriptor.Suffix 枚举值

    # 描述符后缀常量
    NAMESPACE: int = int(scip_pb2.Descriptor.Namespace)
    TYPE: int = int(scip_pb2.Descriptor.Type)
    TERM: int = int(scip_pb2.Descriptor.Term)
    METHOD: int = int(scip_pb2.Descriptor.Method)
    TYPE_PARAMETER: int = int(scip_pb2.Descriptor.TypeParameter)
    PARAMETER: int = int(scip_pb2.Descriptor.Parameter)
    META: int = int(scip_pb2.Descriptor.Meta)
    LOCAL: int = int(scip_pb2.Descriptor.Local)
    MACRO: int = int(scip_pb2.Descriptor.Macro)

    def get_suffix_char(self) -> str:
        """获取描述符后缀字符"""
        suffix_map = {
            self.NAMESPACE: "/",
            self.TYPE: "#",
            self.TERM: ".",
            self.METHOD: "().",
            self.PARAMETER: "()",
            self.TYPE_PARAMETER: "[]",
            self.META: ":",
            self.MACRO: "!",
            self.LOCAL: "",
        }
        return suffix_map.get(self.suffix, "")

    @override
    def __str__(self) -> str:
        """格式化为 SCIP 描述符字符串"""
        suffix_char = self.get_suffix_char()
        if self.disambiguator:
            return f"{self.name}({self.disambiguator}){suffix_char}"
        return f"{self.name}{suffix_char}"


@dataclass(frozen=True)
class Symbol:
    """SCIP 符号表示

    符号用于唯一标识代码中的实体(类、方法、变量等)。
    """

    scheme: str  # 符号方案(通常是编程语言名称)
    package: Package  # 所属包
    descriptors: tuple[Descriptor, ...]  # 描述符元组

    @override
    def __str__(self) -> str:
        """格式化为 SCIP 符号字符串"""
        descriptors_str = "".join(str(d) for d in self.descriptors)
        return f"{self.scheme} {self.package} {descriptors_str}"

    def get_fully_qualified_name(self) -> str:
        """获取完全限定名"""
        return ".".join(d.name for d in self.descriptors)


@dataclass(frozen=True)
class Relationship:
    """符号关系

    定义符号与其他符号之间的关系(如实现、类型定义等)。
    """

    symbol: str  # 相关符号
    is_reference: bool = False  # 是否为引用关系
    is_implementation: bool = False  # 是否为实现关系
    is_type_definition: bool = False  # 是否为类型定义关系
    is_definition: bool = False  # 是否为定义关系


@dataclass(frozen=True)
class Occurrence:
    """符号出现位置

    将源代码中的位置与符号关联起来。
    """

    range: tuple[
        int, ...
    ]  # [start_line, start_char, end_line, end_char] 或 [start_line, start_char, end_char]
    symbol: str  # 关联的符号
    symbol_roles: int = 0  # 符号角色位掩码
    syntax_kind: SyntaxKind | None = None  # 语法类型
    enclosing_range: tuple[int, ...] = field(default_factory=tuple)  # 包围范围
    override_documentation: tuple[str, ...] = field(default_factory=tuple)  # 覆盖文档

    @property
    def is_definition(self) -> bool:
        """是否为定义"""
        return bool(self.symbol_roles & SymbolRole.Definition)

    @property
    def is_reference(self) -> bool:
        """是否为引用"""
        return not self.is_definition

    @property
    def is_import(self) -> bool:
        """是否为导入"""
        return bool(self.symbol_roles & SymbolRole.Import)

    @property
    def is_write_access(self) -> bool:
        """是否为写入访问"""
        return bool(self.symbol_roles & SymbolRole.WriteAccess)

    @property
    def is_read_access(self) -> bool:
        """是否为读取访问"""
        return bool(self.symbol_roles & SymbolRole.ReadAccess)

    @property
    def is_generated(self) -> bool:
        """是否为生成的代码"""
        return bool(self.symbol_roles & SymbolRole.Generated)

    @property
    def is_test(self) -> bool:
        """是否为测试代码"""
        return bool(self.symbol_roles & SymbolRole.Test)

    def get_start_line(self) -> int:
        """获取起始行号(0-based)"""
        return self.range[0]

    def get_start_char(self) -> int:
        """获取起始字符位置"""
        return self.range[1]

    def get_end_line(self) -> int:
        """获取结束行号(0-based)"""
        return self.range[2] if len(self.range) == 4 else self.range[0]

    def get_end_char(self) -> int:
        """获取结束字符位置"""
        return self.range[3] if len(self.range) == 4 else self.range[2]

    def has_enclosing_range(self) -> bool:
        """检查 enclosing_range 是否可用且有效。

        Returns:
            True 如果 enclosing_range 至少有 4 个元素（多行格式）
        """
        return len(self.enclosing_range) >= 4

    def get_enclosing_start_line(self) -> int:
        """获取 enclosing_range 的起始行。

        Returns:
            起始行号（0-based），如果不可用返回 -1
        """
        if self.has_enclosing_range():
            return self.enclosing_range[0]
        return -1

    def get_enclosing_end_line(self) -> int:
        """获取 enclosing_range 的结束行。

        Returns:
            结束行号（0-based），如果不可用返回 -1
        """
        if self.has_enclosing_range():
            return self.enclosing_range[2]
        return -1

    def get_effective_start_line(self) -> int:
        """获取有效起始行，优先使用 enclosing_range。

        Returns:
            如果可用返回 enclosing_range 起始行，否则返回 range 起始行
        """
        enclosing = self.get_enclosing_start_line()
        return enclosing if enclosing >= 0 else self.get_start_line()

    def get_effective_end_line(self) -> int:
        """获取有效结束行，优先使用 enclosing_range。

        Returns:
            如果可用返回 enclosing_range 结束行，否则返回 range 结束行
        """
        enclosing = self.get_enclosing_end_line()
        return enclosing if enclosing >= 0 else self.get_end_line()


@dataclass(frozen=True)
class SymbolInformation:
    """符号元数据

    包含符号的详细信息,如文档、类型、关系等。
    """

    symbol: str  # 符号标识符
    kind: SymbolKind  # 符号类型
    display_name: str  # 显示名称
    documentation: tuple[str, ...] = field(default_factory=tuple)  # Markdown 格式的文档
    relationships: tuple[Relationship, ...] = field(default_factory=tuple)  # 与其他符号的关系
    enclosing_symbol: str | None = None  # 包围符号(用于局部符号)
    signature_documentation: Document | None = None  # 签名文档

    def get_relationships(self, kind: str) -> list[str]:
        """获取特定类型的关系

        Args:
            kind: 关系类型("reference", "implementation", "type_definition", "definition")

        Returns:
            相关符号列表
        """
        result: list[str] = []
        for rel in self.relationships:
            if kind == "reference" and rel.is_reference:
                result.append(rel.symbol)
            elif kind == "implementation" and rel.is_implementation:
                result.append(rel.symbol)
            elif kind == "type_definition" and rel.is_type_definition:
                result.append(rel.symbol)
            elif kind == "definition" and rel.is_definition:
                result.append(rel.symbol)
        return result


@dataclass(frozen=True)
class Document:
    """文档表示

    表示源代码文件及其包含的所有符号信息。
    """

    relative_path: str  # 相对路径
    language: str  # 编程语言
    occurrences: tuple[Occurrence, ...]  # 符号出现位置元组
    symbols: dict[str, SymbolInformation]  # 定义在此文档中的符号
    text: str = ""  # 可选的文档内容
    position_encoding: PositionEncoding = (
        PositionEncoding.UTF8CodeUnitOffsetFromLineStart
    )  # 位置编码方式

    def get_symbol_at(self, line: int, character: int) -> Occurrence | None:
        """获取指定位置的符号

        Args:
            line: 行号(0-based)
            character: 字符位置(0-based)

        Returns:
            该位置的 Occurrence,如果未找到则返回 None
        """
        # 简单实现:线性搜索(可以优化为二分查找)
        for occ in self.occurrences:
            if (
                occ.get_start_line() <= line <= occ.get_end_line()
                and occ.get_start_char() <= character <= occ.get_end_char()
            ):
                return occ
        return None

    def find_occurrences(self, symbol: str) -> list[Occurrence]:
        """查找符号的所有出现

        Args:
            symbol: 符号字符串

        Returns:
            该符号的所有出现位置
        """
        return [occ for occ in self.occurrences if occ.symbol == symbol]

    def find_definition(self, symbol: str) -> Occurrence | None:
        """查找文档中符号的定义出现位置。

        这是一个便捷方法，用于在此文档中搜索特定符号的定义出现。

        Args:
            symbol: 要查找的符号字符串

        Returns:
            表示定义的 Occurrence，如果未找到则返回 None

        Example:
            >>> doc = index.get_document("main.py")
            >>> def_occ = doc.find_definition("main.foo().")
            >>> if def_occ:
            ...     print(f"Defined at line {def_occ.get_start_line()}")
        """
        for occ in self.occurrences:
            if occ.symbol == symbol and occ.is_definition:
                return occ
        return None


@dataclass(frozen=True)
class ToolInfo:
    """工具信息"""

    name: str  # 工具名称
    version: str  # 工具版本
    arguments: tuple[str, ...] = field(default_factory=tuple)  # 命令行参数


@dataclass(frozen=True)
class Metadata:
    """索引元数据"""

    version: int  # SCIP 协议版本
    tool_info: ToolInfo  # 工具信息
    project_root: str  # 项目根目录
    text_document_encoding: TextEncoding = TextEncoding.UTF8  # 文本编码


class IndexStatistics(TypedDict):
    """索引统计信息类型定义"""

    total_documents: int
    total_symbols: int
    total_occurrences: int
    language_distribution: dict[str, int]
    kind_distribution: dict[str, int]


@dataclass
class Index:
    """SCIP 索引根对象

    表示完整的 SCIP 索引,包含所有文档和符号信息。
    """

    metadata: Metadata  # 索引元数据
    documents: tuple[Document, ...]  # 文档元组
    external_symbols: tuple[SymbolInformation, ...] = field(default_factory=tuple)  # 外部符号

    # 内部索引结构(延迟构建)
    _symbol_index: dict[str, list[Occurrence]] = field(default_factory=dict, init=False, repr=False)
    _document_index: dict[str, Document] = field(default_factory=dict, init=False, repr=False)
    _symbol_info_index: dict[str, SymbolInformation] = field(
        default_factory=dict, init=False, repr=False
    )
    _symbol_to_doc_index: dict[str, Document] = field(default_factory=dict, init=False, repr=False)

    def build_indexes(self):
        """构建内部索引以加速查询

        这个方法在解析完成后调用,构建符号索引和文档索引。
        """
        logger.info(f"开始构建索引,共 {len(self.documents)} 个文档")
        logger.debug("开始构建索引结构")
        total_occurrences = 0
        total_symbols = 0

        for doc in self.documents:
            # 文档路径索引
            self._document_index[doc.relative_path] = doc
            logger.debug(f"添加文档到索引: {doc.relative_path}")

            # 符号信息索引
            for symbol, info in doc.symbols.items():
                self._symbol_info_index[symbol] = info
                self._symbol_to_doc_index[symbol] = doc
                total_symbols += 1

            # 符号索引
            for occ in doc.occurrences:
                if occ.symbol:
                    if occ.symbol not in self._symbol_index:
                        self._symbol_index[occ.symbol] = []
                    self._symbol_index[occ.symbol].append(occ)
                    total_occurrences += 1

        logger.info(
            f"索引构建完成: {len(self.documents)} 个文档, "
            f"{total_symbols} 个符号, {total_occurrences} 个出现位置"
        )
        logger.debug(f"符号索引包含 {len(self._symbol_index)} 个唯一符号")

    def get_symbol_info(self, symbol: str) -> SymbolInformation | None:
        """获取符号信息

        Args:
            symbol: 符号字符串

        Returns:
            符号信息对象，如果未找到则返回 None
        """
        return self._symbol_info_index.get(symbol)

    def get_document(self, path: str) -> Document | None:
        """获取指定路径的文档

        Args:
            path: 文档相对路径

        Returns:
            Document 对象,如果未找到则返回 None
        """
        return self._document_index.get(path)

    def get_document_by_symbol(self, symbol: str) -> Document | None:
        """获取定义该符号的文档

        Args:
            symbol: 符号字符串

        Returns:
            Document 对象,如果未找到则返回 None
        """
        return self._symbol_to_doc_index.get(symbol)

    def get_symbol_occurrences(self, symbol: str) -> list[Occurrence]:
        """获取符号的所有出现位置

        Args:
            symbol: 符号字符串

        Returns:
            该符号的所有出现位置列表
        """
        return self._symbol_index.get(symbol, [])

    def list_symbols(self) -> set[str]:
        """列出索引中的所有符号

        Returns:
            符号集合
        """
        return set(self._symbol_index.keys())

    def get_all_definitions(self) -> list[dict]:
        """获取所有符号定义

        这是一个便捷方法，用于获取索引中所有符号的定义信息。
        返回的字典包含了符号的基本信息，无需了解 SCIP 协议细节。

        Returns:
            包含所有定义信息的字典列表，每个字典包含:
            - symbol: 符号字符串
            - display_name: 显示名称
            - kind: 符号类型 (SymbolKind 枚举)
            - kind_name: 类型名称 (字符串)
            - document: 所在文档路径
            - language: 编程语言
            - documentation: 文档注释列表

        Example:
            >>> parser = SCIPParser()
            >>> index = parser.parse_file("project.scip")
            >>> definitions = index.get_all_definitions()
            >>> for d in definitions:
            ...     print(f"{d['display_name']} - {d['kind_name']}")
        """
        definitions = []

        for document in self.documents:
            for symbol_str, symbol_info in document.symbols.items():
                definitions.append(
                    {
                        "symbol": symbol_str,
                        "display_name": symbol_info.display_name,
                        "kind": symbol_info.kind,
                        "kind_name": symbol_info.kind.name,
                        "document": document.relative_path,
                        "language": document.language,
                        "documentation": symbol_info.documentation,
                    }
                )

        return definitions

    def get_definitions_by_kind(self, kind: SymbolKind) -> list[dict]:
        """按符号类型获取定义

        Args:
            kind: SymbolKind 枚举值 (如 SymbolKind.Function)

        Returns:
            该类型的所有定义信息列表

        Example:
            >>> # 获取所有函数定义
            >>> functions = index.get_definitions_by_kind(SymbolKind.Function)
            >>> print(f"找到 {len(functions)} 个函数")
        """
        return [d for d in self.get_all_definitions() if d["kind"] == kind]

    def get_functions(self) -> list[dict]:
        """获取所有函数定义

        Returns:
            函数定义列表

        Example:
            >>> functions = index.get_functions()
            >>> for func in functions:
            ...     print(f"{func['display_name']} 在 {func['document']}")
        """
        return self.get_definitions_by_kind(SymbolKind.Function)

    def get_methods(self) -> list[dict]:
        """获取所有方法定义

        Returns:
            方法定义列表
        """
        return self.get_definitions_by_kind(SymbolKind.Method)

    def get_classes(self) -> list[dict]:
        """获取所有类定义

        Returns:
            类定义列表

        Example:
            >>> classes = index.get_classes()
            >>> for cls in classes:
            ...     print(f"类 {cls['display_name']} 在 {cls['document']}")
        """
        return self.get_definitions_by_kind(SymbolKind.Class)

    def get_interfaces(self) -> list[dict]:
        """获取所有接口定义

        Returns:
            接口定义列表
        """
        return self.get_definitions_by_kind(SymbolKind.Interface)

    def get_definitions_by_kinds(self, kinds: list[SymbolKind]) -> list[dict]:
        """按多个符号类型获取定义

        Args:
            kinds: SymbolKind 枚举值列表

        Returns:
            符合任一类型的定义列表

        Example:
            >>> # 获取所有函数和方法
            >>> results = index.get_definitions_by_kinds([
            ...     SymbolKind.Function,
            ...     SymbolKind.Method
            ... ])
        """
        kind_set = set(kinds)
        return [d for d in self.get_all_definitions() if d["kind"] in kind_set]

    def get_definitions_by_language(self, language: str) -> list[dict]:
        """按编程语言获取定义

        Args:
            language: 编程语言名称 (如 "python", "typescript")

        Returns:
            该语言的所有定义列表

        Example:
            >>> # 获取所有 Python 文件中的定义
            >>> python_defs = index.get_definitions_by_language("python")
        """
        language_lower = language.lower()
        return [d for d in self.get_all_definitions() if d["language"].lower() == language_lower]

    def get_statistics(self) -> IndexStatistics:
        """获取统计信息

        Returns:
            统计信息字典
        """
        from collections import Counter

        language_dist: Counter[str] = Counter()
        kind_dist: Counter[str] = Counter()
        total_symbols = 0
        total_occurrences = 0

        for doc in self.documents:
            total_symbols += len(doc.symbols)
            total_occurrences += len(doc.occurrences)
            language_dist[doc.language] += 1

            for symbol_info in doc.symbols.values():
                kind_dist[symbol_info.kind.name] += 1

        return {
            "total_documents": len(self.documents),
            "total_symbols": total_symbols,
            "total_occurrences": total_occurrences,
            "language_distribution": dict(language_dist),
            "kind_distribution": dict(kind_dist),
        }

    def find_symbols_by_name(self, name: str, exact_match: bool = False) -> list[SymbolInformation]:
        """按名称查找符号

        Args:
            name: 符号名称
            exact_match: 是否精确匹配

        Returns:
            符号信息列表
        """
        # 如果索引已构建，使用 _symbol_info_index 优化查询
        if self._symbol_info_index:
            if exact_match:
                return [
                    info for info in self._symbol_info_index.values() if info.display_name == name
                ]
            else:
                return [
                    info for info in self._symbol_info_index.values() if name in info.display_name
                ]

        # 回退到线性遍历
        results = []
        for doc in self.documents:
            for symbol_info in doc.symbols.values():
                if exact_match:
                    if symbol_info.display_name == name:
                        results.append(symbol_info)
                else:
                    if name in symbol_info.display_name:
                        results.append(symbol_info)
        return results

    def search_symbols(self, query: str) -> list[SymbolInformation]:
        """搜索符号

        Args:
            query: 查询字符串

        Returns:
            符号信息列表
        """
        query_lower = query.lower()
        # 如果索引已构建，使用 _symbol_info_index 优化查询
        if self._symbol_info_index:
            return [
                info
                for info in self._symbol_info_index.values()
                if query_lower in info.display_name.lower() or query_lower in info.symbol.lower()
            ]

        # 回退到线性遍历
        results = []
        for doc in self.documents:
            for symbol_info in doc.symbols.values():
                if (
                    query_lower in symbol_info.display_name.lower()
                    or query_lower in symbol_info.symbol.lower()
                ):
                    results.append(symbol_info)
        return results

    def find_references(self, symbol: str) -> list[Occurrence]:
        """查找符号引用

        Args:
            symbol: 符号字符串

        Returns:
            引用列表
        """
        logger.debug(f"查找符号引用: {symbol}")
        occurrences = self.get_symbol_occurrences(symbol)
        references = [occ for occ in occurrences if occ.is_reference]
        logger.debug(f"找到 {len(references)} 个引用")
        return references

    def find_definition(self, symbol: str) -> Occurrence | None:
        """查找符号定义

        Args:
            symbol: 符号字符串

        Returns:
            定义出现位置
        """
        logger.debug(f"查找符号定义: {symbol}")
        occurrences = self.get_symbol_occurrences(symbol)
        for occ in occurrences:
            if occ.is_definition:
                logger.debug(f"找到定义: {symbol} 在 {occ.range}")
                return occ
        logger.debug(f"未找到定义: {symbol}")
        return None

    def find_implementations(self, symbol: str) -> list[str]:
        """查找实现

        Args:
            symbol: 符号字符串

        Returns:
            实现该符号的符号列表
        """
        implementations = []
        for info in self._symbol_info_index.values():
            for rel in info.relationships:
                if rel.is_implementation and rel.symbol == symbol:
                    implementations.append(info.symbol)
        return implementations

    def find_subtypes(self, symbol: str) -> list[str]:
        """查找子类型

        Args:
            symbol: 父类型符号

        Returns:
            子类型符号列表
        """
        subtypes = []
        for info in self._symbol_info_index.values():
            for rel in info.relationships:
                if rel.is_implementation and rel.symbol == symbol:
                    subtypes.append(info.symbol)
        return subtypes

    def find_supertypes(self, symbol: str) -> list[str]:
        """查找超类型

        Args:
            symbol: 子类型符号

        Returns:
            超类型符号列表
        """
        supertypes = []
        info = self.get_symbol_info(symbol)
        if info:
            for rel in info.relationships:
                if rel.is_implementation:
                    supertypes.append(rel.symbol)
        return supertypes

    def find_callees(self, symbol: str) -> list[str]:
        """查找被调用者

        Args:
            symbol: 调用者符号

        Returns:
            被调用者符号列表
        """
        callees = set()
        definition = self.find_definition(symbol)
        if not definition:
            return []

        doc_path = None
        start_line = definition.get_start_line()
        end_line = definition.get_end_line()

        for cur_doc in self.documents:
            if symbol in cur_doc.symbols:
                for occ in cur_doc.occurrences:
                    if occ.symbol == symbol and occ.is_definition:
                        doc_path = cur_doc.relative_path
                        start_line = occ.get_start_line()
                        end_line = occ.get_end_line()
                        break
            if doc_path:
                break

        if not doc_path:
            return []

        doc = self.get_document(doc_path)
        if doc is None:
            return []

        for occ in doc.occurrences:
            occ_start = occ.get_start_line()
            occ_end = occ.get_end_line()
            if not (occ_end < start_line or occ_start > end_line):
                if occ.is_reference and occ.symbol != symbol:
                    callees.add(occ.symbol)

        return list(callees)

    def find_callers(self, symbol: str) -> list[str]:
        """查找调用者

        Args:
            symbol: 被调用者符号

        Returns:
            调用者符号列表
        """
        callers = set()
        for doc in self.documents:
            for occ in doc.occurrences:
                if occ.symbol == symbol and occ.is_reference:
                    if occ.enclosing_range:
                        start_line = occ.enclosing_range[0]
                        for candidate in doc.occurrences:
                            if candidate.is_definition and candidate.get_start_line() == start_line:
                                callers.add(candidate.symbol)
                                break
        return list(callers)

    def get_call_path(self, from_symbol: str, to_symbol: str) -> list[str] | None:
        """获取调用路径

        Args:
            from_symbol: 起始符号
            to_symbol: 目标符号

        Returns:
            调用路径列表
        """
        import collections

        queue = collections.deque([(from_symbol, [from_symbol])])
        visited = {from_symbol}
        max_depth = 10

        while queue:
            current, path = queue.popleft()
            if len(path) > max_depth:
                continue

            if current == to_symbol:
                return path

            callees = self.find_callees(current)
            for callee in callees:
                if callee == to_symbol:
                    return path + [callee]
                if callee not in visited:
                    visited.add(callee)
                    queue.append((callee, path + [callee]))

        return None

    def find_symbols_by_pattern(self, pattern: str) -> list[SymbolInformation]:
        """按模式查找符号

        Args:
            pattern: 通配符模式

        Returns:
            符号信息列表
        """
        import fnmatch

        results = []
        for doc in self.documents:
            for symbol_info in doc.symbols.values():
                if fnmatch.fnmatch(symbol_info.display_name, pattern):
                    results.append(symbol_info)
        return results

    def analyze_complexity(self, document_path: str | None = None) -> dict[str, Any]:
        """分析代码复杂度

        计算函数/类数量、平均函数长度等指标。

        Args:
            document_path: 可选的文档路径过滤

        Returns:
            包含复杂度指标的字典:
            - function_count: 函数总数
            - class_count: 类总数
            - avg_function_length: 平均函数长度 (行数)
            - max_function_length: 最大函数长度
        """
        docs = [self.get_document(document_path)] if document_path else self.documents
        docs = [d for d in docs if d is not None]

        function_lengths = []
        class_count = 0

        function_kinds = {
            SymbolKind.Function,
            SymbolKind.Method,
            SymbolKind.Constructor,
            SymbolKind.StaticMethod,
            SymbolKind.AbstractMethod,
        }

        for doc in docs:
            for symbol, info in doc.symbols.items():
                if info.kind == SymbolKind.Class:
                    class_count += 1
                elif info.kind in function_kinds:
                    definition = self.find_definition(symbol)
                    if definition:
                        length = definition.get_end_line() - definition.get_start_line() + 1
                        function_lengths.append(length)

        return {
            "function_count": len(function_lengths),
            "class_count": class_count,
            "avg_function_length": (
                sum(function_lengths) / len(function_lengths) if function_lengths else 0.0
            ),
            "max_function_length": max(function_lengths) if function_lengths else 0,
        }

    def find_hotspots(self, n: int = 10) -> list[tuple[str, int]]:
        """查找引用频率最高的符号 (热点)

        Args:
            n: 返回前 N 个热点

        Returns:
            符号标识符和引用次数的元组列表
        """
        from collections import Counter

        counts: Counter[str] = Counter()
        for doc in self.documents:
            for occ in doc.occurrences:
                if occ.is_reference and occ.symbol:
                    counts[occ.symbol] += 1

        defined_symbols = self._symbol_info_index.keys()
        result = [(s, c) for s, c in counts.items() if s in defined_symbols]
        result.sort(key=lambda x: x[1], reverse=True)

        if len(result) < n:
            seen = set(counts.keys())
            for sym in defined_symbols:
                if sym not in seen:
                    result.append((sym, 0))
                    if len(result) >= n:
                        break

        return result[:n]

    def find_dead_code(self, exclude_patterns: list[str] | None = None) -> list[str]:
        """查找未被引用的定义 (死代码)

        Args:
            exclude_patterns: 要排除的符号模式 (fnmatch)

        Returns:
            未被引用的符号标识符列表
        """
        import fnmatch

        dead_code = []
        default_excludes = ["*__init__*", "*main*", "*test*", "*Test*"]
        excludes = exclude_patterns or default_excludes

        for doc in self.documents:
            for symbol in doc.symbols:
                is_excluded = False
                for pattern in excludes:
                    if fnmatch.fnmatch(symbol, pattern):
                        is_excluded = True
                        break
                if is_excluded:
                    continue

                refs = self.find_references(symbol)
                if not refs:
                    dead_code.append(symbol)

        return dead_code

    def get_exported_symbols(self) -> list[SymbolInformation]:
        """获取所有导出的(公开的)符号

        Returns:
            公开定义的符号列表
        """
        exported = []
        for doc in self.documents:
            for symbol, info in doc.symbols.items():
                if symbol.startswith("local "):
                    continue

                if info.display_name.startswith("_") and not info.display_name.startswith("__"):
                    continue

                exported.append(info)
        return exported

    def get_symbols_in_range(
        self, doc_path: str, start_line: int, end_line: int
    ) -> list[Occurrence]:
        """获取指定文档中指定行范围内的符号

        Args:
            doc_path: 文档路径
            start_line: 起始行号
            end_line: 结束行号

        Returns:
            符号出现位置列表
        """
        doc = self.get_document(doc_path)
        if not doc:
            return []

        result = []
        for occ in doc.occurrences:
            occ_start = occ.get_start_line()
            occ_end = occ.get_end_line()
            if not (occ_end < start_line or occ_start > end_line):
                result.append(occ)
        return result

    def get_symbols_at_line(self, doc_path: str, line: int) -> list[Occurrence]:
        """获取指定文档中指定行的符号

        Args:
            doc_path: 文档路径
            line: 行号

        Returns:
            符号出现位置列表
        """
        return self.get_symbols_in_range(doc_path, line, line)
