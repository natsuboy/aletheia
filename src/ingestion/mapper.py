"""SCIP 到 Graph 的映射器"""

from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional
import json

from loguru import logger

from src.models.scip import EdgeType, GraphEdge, GraphNode, MappingResult, NodeLabel
from src.scip_parser import (
    Document,
    Index,
    Occurrence,
    SymbolInformation,
    SymbolKind,
    SymbolRole,
)
from src.scip_parser.graph.call_graph import CallGraphBuilder
from src.scip_parser.graph.inheritance_graph import InheritanceGraphBuilder
from src.scip_parser.graph.dependency_graph import DependencyGraphBuilder


class SCIPToGraphMapper:
    """SCIP 到 Memgraph 的映射器"""

    # SCIP SymbolKind 到 NodeLabel 映射
    KIND_TO_LABEL = {
        # 核心类型
        SymbolKind.Package: NodeLabel.PACKAGE,
        SymbolKind.Module: NodeLabel.MODULE,
        SymbolKind.Class: NodeLabel.CLASS,
        SymbolKind.Struct: NodeLabel.STRUCT,
        SymbolKind.Interface: NodeLabel.INTERFACE,
        SymbolKind.Function: NodeLabel.FUNCTION,
        SymbolKind.Method: NodeLabel.METHOD,
        SymbolKind.StaticMethod: NodeLabel.METHOD,
        SymbolKind.Field: NodeLabel.FIELD,
        SymbolKind.StaticField: NodeLabel.FIELD,
        SymbolKind.Variable: NodeLabel.VARIABLE,
        SymbolKind.Constant: NodeLabel.CONSTANT,
        SymbolKind.TypeAlias: NodeLabel.TYPE_ALIAS,
        # 方法类变体
        SymbolKind.Constructor: NodeLabel.METHOD,
        SymbolKind.AbstractMethod: NodeLabel.METHOD,
        SymbolKind.ProtocolMethod: NodeLabel.METHOD,
        SymbolKind.TraitMethod: NodeLabel.METHOD,
        SymbolKind.TypeClassMethod: NodeLabel.METHOD,
        SymbolKind.PureVirtualMethod: NodeLabel.METHOD,
        SymbolKind.MethodSpecification: NodeLabel.METHOD,
        SymbolKind.SingletonMethod: NodeLabel.METHOD,
        SymbolKind.MethodAlias: NodeLabel.METHOD,
        SymbolKind.Accessor: NodeLabel.METHOD,
        SymbolKind.Getter: NodeLabel.METHOD,
        SymbolKind.Setter: NodeLabel.METHOD,
        # 类/接口类变体
        SymbolKind.Enum: NodeLabel.CLASS,
        SymbolKind.Extension: NodeLabel.CLASS,
        SymbolKind.SingletonClass: NodeLabel.CLASS,
        SymbolKind.Delegate: NodeLabel.CLASS,
        SymbolKind.Mixin: NodeLabel.INTERFACE,
        SymbolKind.Trait: NodeLabel.INTERFACE,
        SymbolKind.Protocol: NodeLabel.INTERFACE,
        # 字段/属性类变体
        SymbolKind.Property: NodeLabel.FIELD,
        SymbolKind.StaticProperty: NodeLabel.FIELD,
        SymbolKind.StaticDataMember: NodeLabel.FIELD,
        SymbolKind.StaticVariable: NodeLabel.VARIABLE,
        SymbolKind.EnumMember: NodeLabel.CONSTANT,
        SymbolKind.Event: NodeLabel.FIELD,
        SymbolKind.StaticEvent: NodeLabel.FIELD,
        # 命名空间/包类变体
        SymbolKind.Namespace: NodeLabel.MODULE,
        SymbolKind.PackageObject: NodeLabel.PACKAGE,
        # 类型类变体
        SymbolKind.TypeParameter: NodeLabel.TYPE_ALIAS,
        SymbolKind.AssociatedType: NodeLabel.TYPE_ALIAS,
        SymbolKind.TypeFamily: NodeLabel.TYPE_ALIAS,
        SymbolKind.TypeClass: NodeLabel.TYPE_ALIAS,
        SymbolKind.Union: NodeLabel.STRUCT,
    }

    def __init__(
        self, project_name: str, strict_mode: bool = False, source_root: Optional[Path] = None
    ):
        """
        Args:
            project_name: 项目名称
            strict_mode: 严格模式(遇到未知符号类型时抛出异常)
            source_root: 可选源码根目录，用于补充文件绝对路径
        """
        self.project_name = project_name
        self.strict_mode = strict_mode
        self.source_root = source_root
        self.stats = defaultdict(int)
        self._warned_kinds: set = set()

    def _file_id(self, relative_path: str) -> str:
        """生成项目隔离的文件节点 ID"""
        return f"file:{self.project_name}:{relative_path}"

    def _symbol_id(self, scip_symbol: str) -> str:
        """生成项目隔离的符号节点 ID"""
        return f"symbol:{self.project_name}:{scip_symbol}"

    def map_index(self, index: Index) -> MappingResult:
        """映射整个 SCIP 索引

        Args:
            index: SCIP 索引对象

        Returns:
            MappingResult: 包含节点、边和统计信息
        """
        logger.info(f"开始映射 SCIP 索引: {self.project_name}")

        nodes: List[GraphNode] = []
        edges: List[GraphEdge] = []
        symbol_to_node: Dict[str, GraphNode] = {}
        existing_node_ids: set[str] = set()

        # 1. 创建项目节点
        project_node = self._create_project_node(index)
        nodes.append(project_node)
        symbol_to_node[f"project:{self.project_name}"] = project_node
        existing_node_ids.add(project_node.id)

        # 2. 处理所有文档
        for doc in index.documents:
            # 创建文件节点
            file_node = self._create_file_node(doc)
            nodes.append(file_node)
            symbol_to_node[self._file_id(doc.relative_path)] = file_node
            existing_node_ids.add(file_node.id)

            # 项目包含文件
            edges.append(
                GraphEdge(
                    from_id=project_node.id,
                    to_id=file_node.id,
                    type=EdgeType.CONTAINS,
                    properties={},
                )
            )

            # 3. 处理文件中的符号定义
            for symbol_info in doc.symbols.values():
                node = self._map_symbol_to_node(symbol_info, doc)
                if node:
                    if node.id in existing_node_ids:
                        symbol_to_node[symbol_info.symbol] = node
                    else:
                        nodes.append(node)
                        symbol_to_node[symbol_info.symbol] = node
                        existing_node_ids.add(node.id)

                    # 文件定义符号
                    edges.append(
                        GraphEdge(
                            from_id=file_node.id,
                            to_id=node.id,
                            type=EdgeType.DEFINES,
                            properties={},
                        )
                    )

                    # 处理符号关系
                    relationship_edges = self._map_relationships(symbol_info, node, symbol_to_node)
                    edges.extend(relationship_edges)

            # 4. 处理引用关系
            occurrence_edges = self._map_occurrences(doc, symbol_to_node, existing_node_ids)
            edges.extend(occurrence_edges)

        # 5. 使用 scip_parser graph builders 提取 CALLS/IMPORTS/INHERITS 关系
        edges.extend(self._extract_calls(index, symbol_to_node))
        edges.extend(self._extract_inherits(index, symbol_to_node))
        edges.extend(self._extract_imports(index, symbol_to_node, existing_node_ids))

        # 7. 边去重（保留属性语义）
        deduped_edges: List[GraphEdge] = []
        seen_keys: set[str] = set()
        for edge in edges:
            key = "|".join([
                edge.from_id,
                edge.to_id,
                edge.type.value,
                json.dumps(edge.properties, sort_keys=True, ensure_ascii=False),
            ])
            if key in seen_keys:
                continue
            seen_keys.add(key)
            deduped_edges.append(edge)
        edges = deduped_edges

        # 6. 统计信息
        self.stats["total_nodes"] = len(nodes)
        self.stats["total_edges"] = len(edges)
        for node in nodes:
            self.stats[f"nodes_{node.label.value}"] += 1
        for edge in edges:
            self.stats[f"edges_{edge.type.value}"] += 1

        logger.info(f"映射完成: {self.stats['total_nodes']} 节点, {self.stats['total_edges']} 边")

        return MappingResult(nodes=nodes, edges=edges, stats=dict(self.stats))

    def _create_project_node(self, index: Index) -> GraphNode:
        """创建项目节点"""
        project_id = f"project:{self.project_name}"
        properties = {
            "name": self.project_name,
            "project_id": self.project_name,  # Add project_id
            "project_root": index.metadata.project_root if index.metadata else "",
            "indexer": index.metadata.tool_info.name
            if index.metadata and index.metadata.tool_info
            else "unknown",
            "indexer_version": index.metadata.tool_info.version
            if index.metadata and index.metadata.tool_info
            else "unknown",
        }
        return GraphNode(id=project_id, label=NodeLabel.PROJECT, properties=properties)

    def _create_file_node(self, doc: Document) -> GraphNode:
        """创建文件节点"""
        file_id = self._file_id(doc.relative_path)
        properties = {
            "path": doc.relative_path,
            "project_id": self.project_name,  # Add project_id
            "language": doc.language,
            "name": Path(doc.relative_path).name,
            "extension": Path(doc.relative_path).suffix,
        }
        if self.source_root:
            properties["absolute_path"] = str((self.source_root / doc.relative_path).resolve())
        return GraphNode(id=file_id, label=NodeLabel.FILE, properties=properties)

    def _map_symbol_to_node(
        self, symbol_info: SymbolInformation, doc: Document
    ) -> Optional[GraphNode]:
        """映射符号到图节点"""
        # 确定节点类型
        label = self.KIND_TO_LABEL.get(symbol_info.kind)
        if label is None:
            if self.strict_mode:
                raise ValueError(f"未知的符号类型: {symbol_info.kind}")
            if symbol_info.kind not in self._warned_kinds:
                logger.debug(f"跳过未映射的符号类型: {symbol_info.kind}")
                self._warned_kinds.add(symbol_info.kind)
            self.stats["skipped_unknown_kind"] += 1
            return None

        # 构建节点 ID (使用 SCIP symbol 作为唯一标识)
        node_id = self._symbol_id(symbol_info.symbol)

        # 提取符号名称
        display_name = symbol_info.display_name or self._extract_name_from_symbol(
            symbol_info.symbol
        )

        # 构建属性
        properties = {
            "scip_id": symbol_info.symbol,
            "name": display_name,
            "project_id": self.project_name,  # Add project_id
            "kind": symbol_info.kind.name if symbol_info.kind else "Unknown",
            "file_path": doc.relative_path,
            "documentation": " ".join(symbol_info.documentation)
            if symbol_info.documentation
            else "",
        }

        # 添加签名文档(如果有)
        if symbol_info.signature_documentation:
            properties["signature"] = symbol_info.signature_documentation.text

        return GraphNode(id=node_id, label=label, properties=properties)

    def _map_relationships(
        self,
        symbol_info: SymbolInformation,
        node: GraphNode,
        symbol_to_node: Dict[str, GraphNode],
    ) -> List[GraphEdge]:
        """映射符号关系"""
        edges = []

        for rel in symbol_info.relationships:
            target_symbol = rel.symbol
            if target_symbol not in symbol_to_node:
                # 目标符号尚未处理,跳过
                self.stats["skipped_missing_target"] += 1
                continue

            target_node = symbol_to_node[target_symbol]

            # 确定关系类型
            if rel.is_implementation:
                # Method -> Method 的 implementation 关系视为 OVERRIDES
                if node.label == NodeLabel.METHOD and target_node.label == NodeLabel.METHOD:
                    edge_type = EdgeType.OVERRIDES
                else:
                    edge_type = EdgeType.IMPLEMENTS
            elif rel.is_type_definition:
                edge_type = EdgeType.TYPE_OF
            elif rel.is_reference:
                edge_type = EdgeType.REFERENCES
            else:
                # 默认为引用
                edge_type = EdgeType.REFERENCES

            edges.append(
                GraphEdge(from_id=node.id, to_id=target_node.id, type=edge_type, properties={})
            )

        return edges

    def _map_occurrences(
        self,
        doc: Document,
        symbol_to_node: Dict[str, GraphNode],
        existing_node_ids: set[str],
    ) -> List[GraphEdge]:
        """映射 Occurrence 为引用/调用关系"""
        edges = []
        # 按符号分组 occurrences
        symbol_occurrences: Dict[str, List[Occurrence]] = defaultdict(list)

        for occ in doc.occurrences:
            if occ.symbol:
                symbol_occurrences[occ.symbol].append(occ)

        # 处理每个符号的 occurrences
        for symbol, occs in symbol_occurrences.items():
            if symbol not in symbol_to_node:
                continue

            target_node = symbol_to_node[symbol]

            # 统计引用
            has_reference = any(not (occ.symbol_roles & SymbolRole.Definition) for occ in occs)

            # 如果有引用,创建 REFERENCES 边
            # (从文件节点到符号节点,表示文件中引用了该符号)
            if has_reference:
                file_id = self._file_id(doc.relative_path)
                if file_id in existing_node_ids:
                    edges.append(
                        GraphEdge(
                            from_id=file_id,
                            to_id=target_node.id,
                            type=EdgeType.REFERENCES,
                            properties={
                                "count": len(
                                    [
                                        o
                                        for o in occs
                                        if not (o.symbol_roles & SymbolRole.Definition)
                                    ]
                                )
                            },
                        )
                    )

        return edges

    def _extract_calls(self, index: Index, symbol_to_node: Dict[str, GraphNode]) -> List[GraphEdge]:
        """使用 CallGraphBuilder 提取 CALLS 关系"""
        edges = []
        try:
            builder = CallGraphBuilder(index)
            call_graph = builder.build()
            for caller, callee in call_graph.edges():
                if caller in symbol_to_node and callee in symbol_to_node:
                    edges.append(GraphEdge(
                        from_id=symbol_to_node[caller].id,
                        to_id=symbol_to_node[callee].id,
                        type=EdgeType.CALLS,
                        properties={"is_direct": True},
                    ))
            logger.info(f"提取 CALLS 关系: {len(edges)} 条")
        except Exception as e:
            logger.warning(f"CALLS 关系提取失败: {e}")
        return edges

    def _extract_inherits(self, index: Index, symbol_to_node: Dict[str, GraphNode]) -> List[GraphEdge]:
        """使用 InheritanceGraphBuilder 提取 INHERITS 关系"""
        edges = []
        try:
            builder = InheritanceGraphBuilder(index)
            inh_graph = builder.build()
            for parent, child in inh_graph.edges():
                if child in symbol_to_node and parent in symbol_to_node:
                    edges.append(GraphEdge(
                        from_id=symbol_to_node[child].id,
                        to_id=symbol_to_node[parent].id,
                        type=EdgeType.INHERITS,
                        properties={},
                    ))
            logger.info(f"提取 INHERITS 关系: {len(edges)} 条")
        except Exception as e:
            logger.warning(f"INHERITS 关系提取失败: {e}")
        return edges

    def _extract_imports(
        self,
        index: Index,
        symbol_to_node: Dict[str, GraphNode],
        existing_node_ids: set[str],
    ) -> List[GraphEdge]:
        """使用 DependencyGraphBuilder 提取 IMPORTS 关系"""
        edges = []
        try:
            builder = DependencyGraphBuilder(index)
            dep_graph = builder.build()
            for src_file, dst_file in dep_graph.edges():
                src_id = self._file_id(src_file)
                dst_id = self._file_id(dst_file)
                if src_id in existing_node_ids and dst_id in existing_node_ids:
                    edges.append(GraphEdge(
                        from_id=src_id,
                        to_id=dst_id,
                        type=EdgeType.IMPORTS,
                        properties={},
                    ))
            logger.info(f"提取 IMPORTS 关系: {len(edges)} 条")
        except Exception as e:
            logger.warning(f"IMPORTS 关系提取失败: {e}")
        return edges

    def _extract_name_from_symbol(self, symbol: str) -> str:
        """从 SCIP symbol 提取显示名称"""
        # SCIP symbol 格式: scheme package descriptors
        # 例如: scip-go go package v1.0.0 `path/to/package`.FunctionName().
        # 我们提取最后一个 descriptor 作为名称
        parts = symbol.split()
        if len(parts) < 3:
            return symbol

        descriptors = " ".join(parts[3:])
        # 移除 SCIP descriptor suffixes (., #, /, etc.)
        name = descriptors.rstrip("./()#[]!:")
        if "`" in name:
            # 提取反引号中的内容
            name = name.split("`")[-1]
        # 提取最后一段(通常是符号名)
        if "." in name:
            name = name.split(".")[-1]

        return name or symbol
