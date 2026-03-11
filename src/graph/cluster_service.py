"""社区聚类服务"""
from typing import Dict
from loguru import logger

from src.graph.client import GraphClient


class ClusterService:
    def __init__(self, graph_client: GraphClient):
        self.graph_client = graph_client

    async def cluster_project(self, project_name: str) -> Dict[str, int]:
        """使用 Memgraph MAGE 算法对项目节点进行社区聚类，并创建 Community 节点和 MEMBER_OF 边"""
        try:
            logger.info(f"Starting community clustering for project: {project_name}")
            
            # 1. 使用 Memgraph project() 和 community_detection 模块运行算法
            # 注意: 如果图较大，MAGE 需要在整图上运行。这里我们直接全图计算，但只更新特定项目的节点。
            query = """
            CALL community_detection.get() YIELD node, community_id
            WHERE node.project_id = $project_name AND node:Symbol
            SET node.community_id = community_id
            RETURN node.id AS node_id, community_id, node.file_path AS path, node.label AS label
            """
            rows = self.graph_client.execute_query(query, {"project_name": project_name})
            
            if not rows:
                logger.info(f"No nodes found to cluster for project {project_name}")
                return {}

            from collections import defaultdict
            import os
            
            # 按 community_id 聚合节点
            communities: Dict[int, list] = defaultdict(list)
            for row in rows:
                communities[row["community_id"]].append(row)
                
            logger.info(f"Detected {len(communities)} communities.")
            
            # 2. 为每个社区生成语义名称并写入 Community 节点
            community_inserts = []
            updates = []
            
            for cid, members in communities.items():
                if len(members) < 3:
                    continue  # 忽略太小的孤立集群
                
                # 寻找出现次数最多的顶层目录
                dir_counts = defaultdict(int)
                for m in members:
                    p = m.get("path")
                    if p:
                        # 提取第一级目录名
                        parts = [part for part in p.split('/') if part]
                        if len(parts) > 1:
                            dir_counts[parts[0]] += 1
                        elif len(parts) == 1:
                            dir_counts["root"] += 1
                
                best_dir = max(dir_counts.items(), key=lambda x: x[1])[0] if dir_counts else "unknown"
                community_name = f"{best_dir}_{cid}"
                community_global_id = f"community:{project_name}:{cid}"
                
                community_inserts.append({
                    "id": community_global_id,
                    "project_id": project_name,
                    "name": community_name,
                    "symbol_count": len(members),
                    "cid": cid
                })
                
                for m in members:
                    updates.append({
                        "node_id": m["node_id"],
                        "community_id": community_global_id
                    })
                    
            if community_inserts:
                # 3. 创建 Community 节点
                create_community_query = """
                UNWIND $batch AS item
                MERGE (c:Community {id: item.id})
                SET c.name = item.name,
                    c.project_id = item.project_id,
                    c.symbol_count = item.symbol_count
                """
                for i in range(0, len(community_inserts), 200):
                    self.graph_client.execute_write(create_community_query, {"batch": community_inserts[i:i+200]})
                
                # 4. 创建 MEMBER_OF 边
                create_edges_query = """
                UNWIND $batch AS item
                MATCH (n) WHERE n.id = item.node_id
                MATCH (c:Community {id: item.community_id})
                MERGE (n)-[:MEMBER_OF]->(c)
                """
                for i in range(0, len(updates), 500):
                    self.graph_client.execute_write(create_edges_query, {"batch": updates[i:i+500]})
                    
            logger.info(f"Successfully clustered {project_name} into {len(community_inserts)} functional communities.")
            return {m["node_id"]: m["community_id"] for m in updates}

        except Exception as e:
            logger.error(f"Failed to run community detection: {e}")
            return {}
