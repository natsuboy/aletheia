"""SCIP 符号字符串解析工具（高精度状态机实现）"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import ClassVar

from src.scip_parser.core.types import Descriptor, Package, SymbolKind

_SIMPLE_ID_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_+-$")


@dataclass(frozen=True)
class ParsedSymbol:
    """已解析的符号信息结构"""

    scheme: str  # 方案名称
    package: Package | None = None  # 包信息
    descriptors: tuple[Descriptor, ...] = field(default_factory=tuple)  # 描述符元组

    def get_fully_qualified_name(self) -> str:
        """获取完全限定名"""
        return ".".join(d.name for d in self.descriptors)

    def get_parent_symbol(self) -> ParsedSymbol | None:
        """获取父符号"""
        if len(self.descriptors) <= 1:
            return None
        return ParsedSymbol(
            scheme=self.scheme, package=self.package, descriptors=self.descriptors[:-1]
        )


class SymbolParser:
    """SCIP 符号解析器

    提供将 SCIP 符号字符串解析为结构化对象的功能,支持缓存以提高性能。
    """

    _parse_cache: ClassVar[dict[str, ParsedSymbol | None]] = {}
    _MAX_CACHE_SIZE: ClassVar[int] = 50000

    @classmethod
    def parse(cls, symbol_str: str) -> ParsedSymbol | None:
        """解析符号字符串

        Args:
            symbol_str: SCIP 格式的符号字符串

        Returns:
            ParsedSymbol 对象,如果解析失败则返回 None
        """
        if symbol_str in cls._parse_cache:
            return cls._parse_cache[symbol_str]

        result = cls._parse_uncached(symbol_str)

        if len(cls._parse_cache) >= cls._MAX_CACHE_SIZE:
            keys = list(cls._parse_cache.keys())[: cls._MAX_CACHE_SIZE // 2]
            for k in keys:
                del cls._parse_cache[k]

        cls._parse_cache[symbol_str] = result
        return result

    @classmethod
    def _parse_uncached(cls, symbol_str: str) -> ParsedSymbol | None:
        """实际执行解析逻辑(无缓存)"""
        if symbol_str.startswith("local "):
            local_id = symbol_str[6:]
            return ParsedSymbol(
                scheme="local",
                descriptors=(Descriptor(name=sys.intern(local_id), suffix=Descriptor.LOCAL),),
            )

        parts, remaining = cls._split_prefix(symbol_str, 4)
        if len(parts) < 4 or not remaining:
            return None

        scheme = sys.intern(parts[0])
        manager = sys.intern(parts[1])
        package_name = sys.intern(parts[2])
        version = sys.intern(parts[3])

        package = Package(manager=manager, name=package_name, version=version)
        descriptors = cls._parse_descriptors(remaining)

        return ParsedSymbol(scheme=scheme, package=package, descriptors=tuple(descriptors))

    @classmethod
    def _split_prefix(cls, symbol_str: str, count: int) -> tuple[list[str], str]:
        parts: list[str] = []
        current: list[str] = []
        i = 0

        while i < len(symbol_str) and len(parts) < count:
            if symbol_str[i] == " ":
                if i + 1 < len(symbol_str) and symbol_str[i + 1] == " ":
                    current.append(" ")
                    i += 2
                else:
                    parts.append("".join(current))
                    current = []
                    i += 1
            else:
                current.append(symbol_str[i])
                i += 1

        if len(parts) == count:
            remaining = "".join(current) + symbol_str[i:]
        else:
            parts.append("".join(current))
            remaining = symbol_str[i:]

        return parts, remaining

    @classmethod
    def _parse_identifier(cls, s: str, pos: int) -> tuple[str, int] | None:
        if pos >= len(s):
            return None

        if s[pos] == "`":
            return cls._parse_escaped_identifier(s, pos)

        return cls._parse_simple_identifier(s, pos)

    @classmethod
    def _parse_simple_identifier(cls, s: str, pos: int) -> tuple[str, int] | None:
        start = pos
        while pos < len(s) and s[pos] in _SIMPLE_ID_CHARS:
            pos += 1

        if pos == start:
            return None
        return s[start:pos], pos

    @classmethod
    def _parse_escaped_identifier(cls, s: str, pos: int) -> tuple[str, int] | None:
        if s[pos] != "`":
            return None

        pos += 1
        content: list[str] = []

        while pos < len(s):
            if s[pos] == "`":
                if pos + 1 < len(s) and s[pos + 1] == "`":
                    content.append("`")
                    pos += 2
                else:
                    pos += 1
                    return "".join(content), pos
            else:
                content.append(s[pos])
                pos += 1

        return None

    @classmethod
    def _parse_descriptors(cls, descriptors_str: str) -> list[Descriptor]:
        descriptors: list[Descriptor] = []
        pos = 0

        while pos < len(descriptors_str):
            result = cls._try_parse_descriptor(descriptors_str, pos)
            if result is None:
                pos += 1
                continue

            descriptor, new_pos = result
            descriptors.append(descriptor)
            pos = new_pos

        return descriptors

    @classmethod
    def _try_parse_descriptor(cls, s: str, pos: int) -> tuple[Descriptor, int] | None:
        if pos >= len(s):
            return None

        if s[pos] == "[":
            return cls._parse_type_parameter(s, pos)

        if s[pos] == "(":
            return cls._parse_parameter(s, pos)

        id_result = cls._parse_identifier(s, pos)
        if id_result is None:
            return None

        name, after_id = id_result

        if after_id >= len(s):
            return None

        next_char = s[after_id]

        if next_char == "(":
            return cls._parse_method(s, pos, name, after_id)

        suffix_map = {
            "/": Descriptor.NAMESPACE,
            "#": Descriptor.TYPE,
            ".": Descriptor.TERM,
            ":": Descriptor.META,
            "!": Descriptor.MACRO,
        }

        if next_char in suffix_map:
            return (
                Descriptor(name=sys.intern(name), suffix=suffix_map[next_char]),
                after_id + 1,
            )

        return None

    @classmethod
    def _parse_method(
        cls, s: str, start: int, name: str, paren_pos: int
    ) -> tuple[Descriptor, int] | None:
        if s[paren_pos] != "(":
            return None

        pos = paren_pos + 1
        disambiguator_start = pos

        while pos < len(s) and s[pos] in _SIMPLE_ID_CHARS:
            pos += 1

        disambiguator = s[disambiguator_start:pos]

        if pos + 1 >= len(s) or s[pos : pos + 2] != ").":
            return None

        return (
            Descriptor(
                name=sys.intern(name),
                disambiguator=disambiguator,
                suffix=Descriptor.METHOD,
            ),
            pos + 2,
        )

    @classmethod
    def _parse_type_parameter(cls, s: str, pos: int) -> tuple[Descriptor, int] | None:
        if s[pos] != "[":
            return None

        pos += 1
        id_result = cls._parse_identifier(s, pos)
        if id_result is None:
            return None

        name, after_id = id_result

        if after_id >= len(s) or s[after_id] != "]":
            return None

        return (
            Descriptor(name=sys.intern(name), suffix=Descriptor.TYPE_PARAMETER),
            after_id + 1,
        )

    @classmethod
    def _parse_parameter(cls, s: str, pos: int) -> tuple[Descriptor, int] | None:
        if s[pos] != "(":
            return None

        pos += 1
        id_result = cls._parse_identifier(s, pos)
        if id_result is None:
            return None

        name, after_id = id_result

        if after_id >= len(s) or s[after_id] != ")":
            return None

        if after_id + 1 < len(s) and s[after_id + 1] == ".":
            return None

        return (
            Descriptor(name=sys.intern(name), suffix=Descriptor.PARAMETER),
            after_id + 1,
        )

    @classmethod
    def format(cls, symbol: ParsedSymbol) -> str:
        """将结构化符号格式化为字符串

        Args:
            symbol: ParsedSymbol 对象

        Returns:
            SCIP 格式的符号字符串
        """
        if symbol.scheme == "local":
            return f"local {symbol.descriptors[0].name}"

        descriptors_str = "".join(cls._format_descriptor(d) for d in symbol.descriptors)

        if symbol.package is None:
            return f"{symbol.scheme} . . . {descriptors_str}"

        return (
            f"{symbol.scheme} "
            f"{symbol.package.manager} "
            f"{symbol.package.name} "
            f"{symbol.package.version} "
            f"{descriptors_str}"
        )

    @classmethod
    def _format_descriptor(cls, descriptor: Descriptor) -> str:
        """格式化单个描述符"""
        if descriptor.suffix == Descriptor.METHOD:
            if descriptor.disambiguator:
                return f"{descriptor.name}({descriptor.disambiguator})."
            return f"{descriptor.name}()."

        if descriptor.suffix == Descriptor.PARAMETER:
            return f"({descriptor.name})"

        if descriptor.suffix == Descriptor.TYPE_PARAMETER:
            return f"[{descriptor.name}]"

        suffix_chars = {
            Descriptor.NAMESPACE: "/",
            Descriptor.TYPE: "#",
            Descriptor.TERM: ".",
            Descriptor.META: ":",
            Descriptor.MACRO: "!",
            Descriptor.LOCAL: "",
        }
        return f"{descriptor.name}{suffix_chars.get(descriptor.suffix, '')}"

    @classmethod
    def infer_metadata(cls, symbol_str: str) -> tuple[str, SymbolKind]:
        """从符号字符串推断显示名称和类型

        Args:
            symbol_str: 符号字符串

        Returns:
            (显示名称, 符号类型) 元组
        """
        parsed = cls.parse(symbol_str)
        if not parsed or not parsed.descriptors:
            return "", SymbolKind.Unspecified

        last_desc = parsed.descriptors[-1]
        name = last_desc.name

        suffix_to_kind = {
            Descriptor.NAMESPACE: SymbolKind.Namespace,
            Descriptor.TYPE: SymbolKind.Type,
            Descriptor.TERM: SymbolKind.Variable,
            Descriptor.METHOD: SymbolKind.Method,
            Descriptor.TYPE_PARAMETER: SymbolKind.TypeParameter,
            Descriptor.PARAMETER: SymbolKind.Parameter,
            Descriptor.META: SymbolKind.Unspecified,
            Descriptor.MACRO: SymbolKind.Macro,
            Descriptor.LOCAL: SymbolKind.Variable,
        }

        kind = suffix_to_kind.get(last_desc.suffix, SymbolKind.Unspecified)
        return name, kind
