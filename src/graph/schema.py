"""图数据库 Schema 初始化"""
from loguru import logger

from src.graph.client import GraphClient


class SchemaInitializer:
    """Schema 初始化器"""

    def __init__(self, client: GraphClient):
        self.client = client

    def initialize(self) -> None:
        """初始化 Schema"""
        logger.info("Initializing Memgraph schema...")

        # 创建索引
        self._create_indexes()

        # 创建约束
        self._create_constraints()

        logger.info("Schema initialization completed")

    def _create_indexes(self) -> None:
        """创建索引"""
        indexes = [
            # 项目索引
            "CREATE INDEX ON :Project(name);",
            "CREATE INDEX ON :Project(path);",
            # 文件索引
            "CREATE INDEX ON :File(path);",
            # 符号索引
            "CREATE INDEX ON :Symbol(scip_id);",
            "CREATE INDEX ON :Symbol(name);",
            # 包/模块索引
            "CREATE INDEX ON :Package(name);",
            "CREATE INDEX ON :Module(name);",
            # 类索引
            "CREATE INDEX ON :Class(name);",
            # 函数/方法索引
            "CREATE INDEX ON :Function(name);",
            "CREATE INDEX ON :Method(name);",
            # 接口索引
            "CREATE INDEX ON :Interface(name);",
            # qualified_name 索引 (符号搜索性能)
            "CREATE INDEX ON :Function(scip_id);",
            "CREATE INDEX ON :Method(scip_id);",
            "CREATE INDEX ON :Class(scip_id);",
            "CREATE INDEX ON :Interface(scip_id);",
            # project_id 索引 (项目级查询)
            "CREATE INDEX ON :File(project_id);",
            "CREATE INDEX ON :Function(project_id);",
            "CREATE INDEX ON :Method(project_id);",
            "CREATE INDEX ON :Class(project_id);",
            # id 属性索引（供 MERGE {id: ...} 使用，避免全表扫描）
            "CREATE INDEX ON :Project(id);",
            "CREATE INDEX ON :File(id);",
            "CREATE INDEX ON :Package(id);",
            "CREATE INDEX ON :Module(id);",
            "CREATE INDEX ON :Class(id);",
            "CREATE INDEX ON :Struct(id);",
            "CREATE INDEX ON :Interface(id);",
            "CREATE INDEX ON :Function(id);",
            "CREATE INDEX ON :Method(id);",
            "CREATE INDEX ON :Field(id);",
            "CREATE INDEX ON :Variable(id);",
            "CREATE INDEX ON :Constant(id);",
            "CREATE INDEX ON :TypeAlias(id);",
            "CREATE INDEX ON :Community(id);",
            "CREATE INDEX ON :Process(id);",
        ]

        for index_query in indexes:
            try:
                self.client.execute_write(index_query)
                logger.debug(f"Created index: {index_query}")
            except Exception as e:
                # 索引可能已存在,忽略错误
                logger.debug(f"Index creation skipped: {e}")

    def _create_constraints(self) -> None:
        """创建约束"""
        # Memgraph 的约束语法与 Neo4j 不同
        # 这里使用唯一性约束
        constraints = [
            "CREATE CONSTRAINT ON (p:Project) ASSERT p.name IS UNIQUE;",
            "CREATE CONSTRAINT ON (f:File) ASSERT f.path IS UNIQUE;",
            "CREATE CONSTRAINT ON (s:Symbol) ASSERT s.scip_id IS UNIQUE;",
        ]

        for constraint_query in constraints:
            try:
                self.client.execute_write(constraint_query)
                logger.debug(f"Created constraint: {constraint_query}")
            except Exception as e:
                # 约束可能已存在,忽略错误
                logger.debug(f"Constraint creation skipped: {e}")

    def clear_all(self) -> None:
        """清空所有数据"""
        logger.warning("Clearing all data from Memgraph...")
        self.client.execute_write("MATCH (n) DETACH DELETE n;")
        logger.info("All data cleared")
