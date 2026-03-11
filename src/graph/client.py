"""Memgraph 客户端"""
from typing import List, Dict, Any, Optional
from neo4j import GraphDatabase, Driver, Transaction
from neo4j.exceptions import (
    ServiceUnavailable,
    AuthError,
    ClientError,
    DatabaseError,
    TransactionError,
)
from loguru import logger

from src.backend.config import get_settings
from src.backend.security import CypherSanitizer
from src.utils.retry import with_retry, RetryConfig

_graph_retry = with_retry(RetryConfig(
    max_retries=3, base_delay=0.5, backoff_factor=2.0,
    retryable_exceptions=(ServiceUnavailable, TransactionError),
))

from src.graph.exceptions import (
    GraphConnectionError,
    GraphQueryError,
    GraphDatabaseError,
    GraphTransactionError,
    GraphValidationError,
)


class GraphClient:
    """Memgraph 图数据库客户端"""

    def __init__(self):
        self._driver: Optional[Driver] = None
        self._settings = get_settings()
        self._is_connected = False

    def connect(self) -> None:
        """连接到 Memgraph 数据库"""
        uri = f"bolt://{self._settings.memgraph_host}:{self._settings.memgraph_port}"

        try:
            self._driver = GraphDatabase.driver(
                uri,
                auth=(self._settings.memgraph_username, self._settings.memgraph_password)
                if self._settings.memgraph_username
                else None,
                connection_timeout=30,
                max_transaction_retry_time=60.0,
                connection_acquisition_timeout=30.0,
            )
            # 验证连接
            self._driver.verify_connectivity()
            self._is_connected = True
            logger.info(f"Connected to Memgraph at {uri}")

        except AuthError as e:
            raise GraphConnectionError(
                message="Authentication failed for Memgraph",
                host=self._settings.memgraph_host,
                port=self._settings.memgraph_port,
                original_error=e
            )

        except ServiceUnavailable as e:
            raise GraphConnectionError(
                message="Memgraph service is unavailable",
                host=self._settings.memgraph_host,
                port=self._settings.memgraph_port,
                original_error=e
            )

        except Exception as e:
            raise GraphConnectionError(
                message="Failed to connect to Memgraph",
                host=self._settings.memgraph_host,
                port=self._settings.memgraph_port,
                original_error=e
            )

    def close(self) -> None:
        """关闭数据库连接"""
        if self._driver:
            try:
                self._driver.close()
                self._is_connected = False
                logger.info("Memgraph connection closed")
            except Exception as e:
                logger.warning(f"Error closing Memgraph connection: {e}")

    def _ensure_connected(self) -> None:
        """确保数据库已连接"""
        if not self._driver or not self._is_connected:
            raise GraphConnectionError(
                message="Database not connected. Call connect() first."
            )

    @_graph_retry
    def execute_query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
        timeout: int = 120,
    ) -> List[Dict[str, Any]]:
        """执行查询并返回结果"""
        self._ensure_connected()

        try:
            with self._driver.session() as session:
                result = session.run(query, parameters or {}, timeout=timeout)
                return [record.data() for record in result]

        except ClientError as e:
            raise GraphQueryError(
                message="Query syntax or execution error",
                query=query,
                parameters=parameters,
                original_error=e
            )

        except DatabaseError as e:
            raise GraphDatabaseError(
                message="Database error during query execution",
                original_error=e
            )

        except Exception as e:
            raise GraphQueryError(
                message="Unexpected error during query execution",
                query=query,
                parameters=parameters,
                original_error=e
            )

    @_graph_retry
    def execute_write(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> None:
        """执行写入操作"""
        self._ensure_connected()

        try:
            with self._driver.session() as session:
                session.execute_write(lambda tx: tx.run(query, parameters or {}, timeout=120))

        except TransactionError as e:
            raise GraphTransactionError(
                message="Write transaction failed",
                original_error=e
            )

        except ClientError as e:
            raise GraphQueryError(
                message="Write query error",
                query=query,
                parameters=parameters,
                original_error=e
            )

        except Exception as e:
            raise GraphTransactionError(
                message="Unexpected error during write operation",
                original_error=e
            )

    def execute_write_no_retry(
        self, query: str, parameters: Optional[Dict[str, Any]] = None, timeout: int = 120
    ) -> None:
        """执行写入操作（禁用事务重试，适合不可恢复错误快速失败场景）。"""
        self._ensure_connected()
        try:
            with self._driver.session() as session:
                result = session.run(query, parameters or {}, timeout=timeout)
                result.consume()
        except TransactionError as e:
            raise GraphTransactionError(
                message="Write (no-retry) transaction failed",
                original_error=e,
            )
        except ClientError as e:
            raise GraphQueryError(
                message="Write (no-retry) query error",
                query=query,
                parameters=parameters,
                original_error=e,
            )
        except Exception as e:
            raise GraphTransactionError(
                message="Unexpected error during write (no-retry)",
                original_error=e,
            )

    def batch_insert(self, queries: List[tuple[str, Dict[str, Any]]]) -> None:
        """批量插入数据"""
        self._ensure_connected()

        try:
            with self._driver.session() as session:
                def _batch_write(tx: Transaction):
                    for query, params in queries:
                        tx.run(query, params)

                session.execute_write(_batch_write)
                logger.info(f"Batch inserted {len(queries)} queries")

        except TransactionError as e:
            raise GraphTransactionError(
                message=f"Batch insert of {len(queries)} queries failed",
                original_error=e
            )

        except Exception as e:
            raise GraphTransactionError(
                message="Unexpected error during batch insert",
                original_error=e
            )

    def batch_create_nodes(
        self,
        nodes: List[Dict[str, Any]],
        batch_size: int = 1000,
        merge: bool = True,
    ) -> int:
        """使用 UNWIND 批量创建节点

        Args:
            nodes: 节点列表，每个节点包含 id, label, properties
            batch_size: 每批次大小

        Returns:
            创建的节点总数
        """
        if not nodes:
            return 0

        # 验证并清理所有标签（防止 Cypher 注入）
        for node in nodes:
            if 'label' in node:
                label = node['label']
                try:
                    # 使用 CypherSanitizer 验证标签
                    node['label'] = CypherSanitizer.sanitize_identifier(label)
                except Exception as e:
                    logger.error(f"无效的节点标签 '{label}': {e}")
                    raise GraphValidationError(
                        message=f"无效的节点标签",
                        field="label",
                        value=label,
                        original_error=e
                    )

        total_created = 0
        write_keyword = "MERGE" if merge else "CREATE"
        has_label = bool(nodes and 'label' in nodes[0])
        if has_label:
            # 按标签全局分组，减少 query 切换和会话开销
            from collections import defaultdict
            by_label = defaultdict(list)
            for node in nodes:
                # 确保 properties 包含 id 字段
                if 'properties' not in node:
                    node['properties'] = {}
                node['properties']['id'] = node['id']
                by_label[node.get('label', 'Node')].append(node)

            for label, label_nodes in by_label.items():
                label_query = f"""
                UNWIND $nodes AS node
                {write_keyword} (n:{label} {{id: node.id}})
                SET n += node.properties
                """
                for i in range(0, len(label_nodes), batch_size):
                    batch = label_nodes[i:i + batch_size]
                    self.execute_write(label_query, {"nodes": batch})
                    total_created += len(batch)
        else:
            query = """
            UNWIND $nodes AS node
            """ + write_keyword + """ (n {id: node.id})
            SET n += node.properties
            """
            for i in range(0, len(nodes), batch_size):
                batch = nodes[i:i + batch_size]
                self.execute_write(query, {"nodes": batch})
                total_created += len(batch)

        logger.info(f"Batch created {total_created} nodes")
        return total_created

    def batch_create_edges(
        self,
        edges: List[Dict[str, Any]],
        batch_size: int = 1000,
        pre_grouped: bool = False,
        merge: bool = True,
    ) -> int:
        """使用 UNWIND 批量创建边

        Args:
            edges: 边列表，每个边包含 from_id, to_id, type, properties
            batch_size: 每批次大小
            pre_grouped: 若为 True，表示调用方已按 edge_type 分好组，跳过内部分组

        Returns:
            创建的边总数
        """
        if not edges:
            return 0

        # 验证并清理所有边类型（防止 Cypher 注入）
        for edge in edges:
            if 'type' in edge:
                edge_type = edge['type']
                try:
                    edge['type'] = CypherSanitizer.sanitize_identifier(edge_type)
                except Exception as e:
                    logger.error(f"无效的边类型 '{edge_type}': {e}")
                    raise GraphValidationError(
                        message=f"无效的边类型",
                        field="type",
                        value=edge_type,
                        original_error=e
                    )

        if pre_grouped:
            # 调用方已分组，batch 内所有边类型相同，直接取第一个元素的 type
            edge_type = edges[0]['type']
            from_label = edges[0].get("from_label", "")
            to_label = edges[0].get("to_label", "")
            from_clause = f"(from:{from_label} {{id: edge.from_id}})" if from_label else "(from {id: edge.from_id})"
            to_clause = f"(to:{to_label} {{id: edge.to_id}})" if to_label else "(to {id: edge.to_id})"
            rel_keyword = "MERGE" if merge else "CREATE"
            query = f"""
            UNWIND $edges AS edge
            MATCH {from_clause}
            MATCH {to_clause}
            {rel_keyword} (from)-[r:{edge_type}]->(to)
            SET r += edge.properties
            """
            total_created = 0
            with self._driver.session() as session:
                for i in range(0, len(edges), batch_size):
                    b = edges[i:i + batch_size]
                    session.execute_write(
                        lambda tx, nodes=b: tx.run(query, {"edges": nodes}, timeout=120)
                    )
                    total_created += len(b)
            logger.info(f"Batch created {total_created} edges")
            return total_created

        total_created = 0

        # 按边类型分组（因为Cypher关系类型不支持参数化）
        from collections import defaultdict
        by_type = defaultdict(list)
        for edge in edges:
            edge_type = edge.get('type', 'RELATES_TO')
            by_type[edge_type].append(edge)

        for edge_type, type_edges in by_type.items():
            for i in range(0, len(type_edges), batch_size):
                batch = type_edges[i:i+batch_size]

                # 节点已在前一步插入，使用 MATCH 避免无标签全表扫描
                query = f"""
                UNWIND $edges AS edge
                MATCH (from) WHERE from.id = edge.from_id
                MATCH (to) WHERE to.id = edge.to_id
                {"MERGE" if merge else "CREATE"} (from)-[r:{edge_type}]->(to)
                SET r += edge.properties
                """

                self.execute_write(query, {"edges": batch})
                total_created += len(batch)

        logger.info(f"Batch created {total_created} edges")
        return total_created

    def health_check(self) -> bool:
        """健康检查"""
        try:
            self.execute_query("RETURN 1 as health")
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
