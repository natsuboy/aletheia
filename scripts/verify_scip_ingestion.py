#!/usr/bin/env python3
"""
快速验证SCIP解析和Memgraph插入
支持可选源码路径，用于提取代码片段和签名
"""

import sys
from pathlib import Path
from typing import Optional
from collections import defaultdict
from datetime import datetime

from src.scip_parser import SCIPParser
from src.ingestion.mapper import SCIPToGraphMapper
from src.ingestion.service import IngestionService
from src.graph import GraphClient
from loguru import logger


def main():
    """主函数"""
    if len(sys.argv) < 3:
        print("Usage: python verify_scip_ingestion.py <scip_file> <project_name> [source_root]")
        print()
        print("Arguments:")
        print("  scip_file    : Path to .scip index file (required)")
        print("  project_name  : Project name (required)")
        print("  source_root  : Path to source code directory (optional)")
        print()
        print("Examples:")
        print("  # Basic: no source code extraction")
        print("  python verify_scip_ingestion.py index.scip goods-manager-svc")
        print()
        print("  # With source code: extract code snippets and signatures")
        print("  python verify_scip_ingestion.py index.scip goods-manager-svc /path/to/source")
        sys.exit(1)

    scip_path = sys.argv[1]
    project_name = sys.argv[2]
    source_root: Optional[str] = sys.argv[3] if len(sys.argv) > 3 else None

    print(f"\n{'=' * 70}")
    print(f"SCIP Ingestion Verification")
    print(f"{'=' * 70}")
    print(f"SCIP File    : {scip_path}")
    print(f"Project Name : {project_name}")
    print(f"Source Root  : {source_root or 'None (no code extraction)'}")
    print(f"{'=' * 70}\n")

    # 验证SCIP文件存在
    scip_file = Path(scip_path)
    if not scip_file.exists():
        logger.error(f"SCIP file not found: {scip_path}")
        sys.exit(1)

    # 验证源码路径（如果提供）
    if source_root:
        source_path = Path(source_root)
        if not source_path.exists():
            logger.error(f"Source root not found: {source_root}")
            sys.exit(1)
        logger.info(f"Source root validated: {source_path}")

    start_time = datetime.now()

    try:
        # Step 1: Parse SCIP
        logger.info("Step 1/4: Parsing SCIP file...")
        parser = SCIPParser()
        index = parser.parse_file(scip_path)
        parse_time = datetime.now() - start_time
        logger.info(
            f"SCIP parsed: {len(index.documents)} documents in {parse_time.total_seconds():.2f}s"
        )

        # Step 2: Map to graph
        logger.info("Step 2/4: Mapping SCIP to graph structure...")
        mapper = SCIPToGraphMapper(project_name=project_name, strict_mode=False)
        result = mapper.map_index(index)
        map_time = datetime.now() - start_time
        logger.info(
            f"Mapped: {result.stats['total_nodes']} nodes, {result.stats['total_edges']} edges in {(map_time - parse_time).total_seconds():.2f}s"
        )

        # Step 3: Insert into Memgraph
        logger.info("Step 3/4: Inserting into Memgraph...")
        client = GraphClient()
        client.connect()

        try:
            service = IngestionService(graph_client=client)
            service._insert_nodes(result.nodes)
            insert_nodes_time = datetime.now() - start_time
            logger.info(
                f"Nodes inserted: {len(result.nodes)} in {(insert_nodes_time - map_time).total_seconds():.2f}s"
            )

            service._insert_edges(result.edges)
            insert_edges_time = datetime.now() - start_time
            logger.info(
                f"Edges inserted: {len(result.edges)} in {(insert_edges_time - insert_nodes_time).total_seconds():.2f}s"
            )

            # Step 4: Query and display statistics
            logger.info("Step 4/4: Querying database statistics...")
            stats = _query_statistics(client, project_name)

            total_time = datetime.now() - start_time

            # Display summary
            _print_summary(
                scip_path=scip_path,
                project_name=project_name,
                source_root=source_root,
                parse_time=parse_time.total_seconds(),
                map_time=(map_time - parse_time).total_seconds(),
                insert_nodes_time=(insert_nodes_time - map_time).total_seconds(),
                insert_edges_time=(insert_edges_time - insert_nodes_time).total_seconds(),
                total_time=total_time.total_seconds(),
                stats=stats,
            )

        finally:
            client.close()

        logger.success("✓ Verification completed successfully!")

    except Exception as e:
        logger.error(f"Verification failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


def _query_statistics(client: GraphClient, project_name: str) -> dict:
    """查询Memgraph统计信息"""
    stats = {
        "total_nodes": 0,
        "total_edges": 0,
        "node_types": defaultdict(int),
        "edge_types": defaultdict(int),
    }

    # 总节点数
    result = client.execute_query("MATCH (n) RETURN count(n) AS count")
    stats["total_nodes"] = result[0]["count"]

    # 总边数
    result = client.execute_query("MATCH ()-[r]->() RETURN count(r) AS count")
    stats["total_edges"] = result[0]["count"]

    # 节点类型分布
    result = client.execute_query("""
        MATCH (n)
        RETURN labels(n) as labels, count(*) as count
    """)
    for row in result:
        stats["node_types"][str(row["labels"])] = row["count"]

    # 边类型分布
    result = client.execute_query("""
        MATCH ()-[r]->()
        RETURN type(r) as type, count(*) as count
    """)
    for row in result:
        stats["edge_types"][row["type"]] = row["count"]

    return stats


def _print_summary(**kwargs):
    """打印摘要信息"""
    print(f"\n{'=' * 70}")
    print(f"VERIFICATION SUMMARY")
    print(f"{'=' * 70}")

    print(f"\n📁 File Information:")
    print(f"  SCIP File   : {kwargs['scip_path']}")
    print(f"  Project Name : {kwargs['project_name']}")
    print(f"  Source Root : {kwargs['source_root'] or 'None'}")

    print(f"\n⏱️  Performance:")
    print(f"  Parse SCIP     : {kwargs['parse_time']:.2f}s")
    print(f"  Map Graph      : {kwargs['map_time']:.2f}s")
    print(f"  Insert Nodes   : {kwargs['insert_nodes_time']:.2f}s")
    print(f"  Insert Edges   : {kwargs['insert_edges_time']:.2f}s")
    print(f"  Total Time     : {kwargs['total_time']:.2f}s")

    stats = kwargs["stats"]
    print(f"\n📊 Database Statistics:")
    print(f"  Total Nodes    : {stats['total_nodes']:,}")
    print(f"  Total Edges    : {stats['total_edges']:,}")

    print(f"\n  Node Types:")
    for node_type, count in sorted(stats["node_types"].items(), key=lambda x: -x[1]):
        print(f"    {node_type:30s} : {count:,}")

    if stats["edge_types"]:
        print(f"\n  Edge Types:")
        for edge_type, count in sorted(stats["edge_types"].items(), key=lambda x: -x[1]):
            print(f"    {edge_type:20s} : {count:,}")

    print(f"\n{'=' * 70}\n")


if __name__ == "__main__":
    main()
