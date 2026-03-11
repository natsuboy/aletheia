"""摄取服务 - 编排 SCIP 索引到 Memgraph 的完整流程"""

import asyncio
import csv
import json
import subprocess
import shutil
import uuid
from pathlib import Path
from typing import Optional

from loguru import logger

from src.graph.client import GraphClient
from src.graph.bulk_loader import BulkLoader
from src.ingestion.mapper import SCIPToGraphMapper
from src.ingestion.indexer import IndexerManager
from src.models.scip import MappingResult
from src.scip_parser import SCIPParser
from src.backend.job_store import job_store
from src.backend.config import get_settings
from src.graph.snapshot_store import GraphSnapshotKeys, sync_get_json, sync_set_json, default_meta, now_iso


class IngestionService:
    """摄取服务 - 完整的 SCIP → Memgraph 流程"""

    def __init__(self, graph_client: GraphClient = None, batch_size: int = 1000):
        """
        Args:
            graph_client: Memgraph 客户端
            batch_size: 批量插入大小
        """
        if graph_client is None:
            graph_client = GraphClient()
            graph_client.connect()

        settings = get_settings()
        self.graph_client = graph_client
        self.batch_size = batch_size
        self.bulk_chunk_rows = settings.bulk_chunk_rows
        self.bulk_load_timeout_seconds = settings.bulk_load_timeout_seconds
        self.full_rebuild_only = bool(settings.full_rebuild_only)
        self.full_rebuild_clear_all = bool(settings.full_rebuild_clear_all)
        self.full_rebuild_verify_edges = bool(settings.full_rebuild_verify_edges)
        self.indexer = IndexerManager()
        self.work_dir = Path("/data/aletheia")
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.snapshot_dir = Path(settings.csv_staging_write_dir)
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self.bulk_loader = BulkLoader(
            self.graph_client,
            write_root=self.snapshot_dir,
            read_root=Path(settings.csv_staging_read_dir),
            load_timeout_seconds=self.bulk_load_timeout_seconds,
        )

    async def ingest(
        self,
        repo_url: str,
        language: str,
        project_name: str,
        branch: str = "main",
        job_id: str = None,
    ):
        """
        完整摄取流程
        """
        logger.info(f"Starting ingestion for {repo_url} (job_id={job_id})")

        try:
            # 直接克隆,不检查completed_stages
            if job_id:
                self._update_job_status(job_id, "cloning", 0, "正在克隆仓库...")
            repo_path = await self._git_clone(repo_url, project_name, branch)

            # 直接索引,不检查completed_stages
            if job_id:
                self._update_job_status(job_id, "indexing", 20, "正在生成索引...")
            loop = asyncio.get_event_loop()
            scip_path = await loop.run_in_executor(
                None, self.indexer.index_project, repo_path, language
            )

            # 直接插入,不检查completed_stages
            if job_id:
                self._update_job_status(job_id, "parsing", 40, "正在解析索引...")
            import functools
            loop = asyncio.get_event_loop()
            fn = functools.partial(
                self.ingest_scip_file,
                scip_path,
                project_name,
                job_id=job_id,
            )
            await loop.run_in_executor(None, fn)

            # 社区聚类
            try:
                from src.graph.cluster_service import ClusterService
                cluster_service = ClusterService(self.graph_client)
                await cluster_service.cluster_project(project_name)
            except Exception as e:
                logger.warning(f"Community clustering failed (non-critical): {e}")

            if job_id:
                self._update_job_status(job_id, "completed", 100, "摄取完成", write_phase="completed")
        except Exception as e:
            logger.error(f"Ingestion failed: {e}")
            if job_id:
                self._update_job_status(job_id, "failed", 0, str(e), error=str(e))
            raise

    def _ensure_graph_indexes(self) -> None:
        """确保写入关键索引存在（幂等/尽力而为）。"""
        # Memgraph 某些版本不支持 IF NOT EXISTS，重复创建会报错，故这里吞掉异常。
        ddl_statements = [
            "CREATE INDEX ON :Project(id)",
            "CREATE INDEX ON :File(id)",
            "CREATE INDEX ON :Package(id)",
            "CREATE INDEX ON :Module(id)",
            "CREATE INDEX ON :Function(id)",
            "CREATE INDEX ON :Method(id)",
            "CREATE INDEX ON :Class(id)",
            "CREATE INDEX ON :Struct(id)",
            "CREATE INDEX ON :Interface(id)",
            "CREATE INDEX ON :Field(id)",
            "CREATE INDEX ON :Variable(id)",
            "CREATE INDEX ON :Constant(id)",
            "CREATE INDEX ON :TypeAlias(id)",
            "CREATE INDEX ON :Community(id)",
            "CREATE INDEX ON :Process(id)",
        ]
        for ddl in ddl_statements:
            try:
                self.graph_client.execute_write(ddl)
            except Exception:
                pass

    @staticmethod
    def _deduplicate_mapping_result(result: MappingResult) -> MappingResult:
        """导入前去重，降低边写入成本。"""
        node_by_id = {}
        for node in result.nodes:
            node_by_id[node.id] = node

        seen_edges = set()
        dedup_edges = []
        for edge in result.edges:
            key = (edge.from_id, edge.type.value, edge.to_id)
            if key in seen_edges:
                continue
            seen_edges.add(key)
            dedup_edges.append(edge)

        result.nodes = list(node_by_id.values())
        result.edges = dedup_edges
        result.stats["total_nodes"] = len(result.nodes)
        result.stats["total_edges"] = len(result.edges)
        return result

    async def _git_clone(self, repo_url: str, project_name: str, branch: str) -> Path:
        """克隆 Git 仓库"""
        target_path = self.work_dir / project_name

        # 如果目录已存在，先删除
        if target_path.exists():
            logger.info(f"Removing existing directory: {target_path}")
            shutil.rmtree(target_path)

        logger.info(f"Cloning {repo_url} to {target_path}")

        cmd = ["git", "clone", "--depth", "1", "--branch", branch, repo_url, str(target_path)]

        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = f"Git clone failed: {stderr.decode()}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        return target_path

    def _update_job_status(
        self,
        job_id: str,
        stage: str,
        progress: float,
        message: str = None,
        error: str = None,
        project_name: str = None,
        write_phase: str | None = None,
        items_total: int | None = None,
        items_done: int | None = None,
    ):
        """更新任务状态并发布到 Redis 频道

        Args:
            project_name: 可选，直接传入可避免额外的 Redis GET
        """
        from datetime import datetime
        updates = {"stage": stage, "progress": progress, "updated_at": datetime.now().isoformat()}
        if message:
            updates["message"] = message
        if write_phase is not None:
            updates["write_phase"] = write_phase
        if items_total is not None:
            updates["items_total"] = items_total
        if items_done is not None:
            updates["items_done"] = items_done
        if error:
            updates["status"] = "failed"
            updates["error"] = error
        elif stage == "completed":
            updates["status"] = "completed"
        else:
            updates["status"] = "running"

        job_store.update(job_id, updates)

        # 发布进度到 Redis pub/sub 频道
        if project_name:
            job_store.redis.publish(f"ingestion:{project_name}", json.dumps(updates))
        else:
            # 降级：从 Redis 读取（兼容未传 project_name 的旧调用方）
            job_data = job_store.get(job_id)
            if job_data:
                pname = job_data.get("project_name", "")
                if pname:
                    job_store.redis.publish(f"ingestion:{pname}", json.dumps(updates))

        # 终态时清理 active-job 并更新快照元信息
        final_status = updates.get("status")
        if final_status in {"completed", "failed"}:
            terminal_project = project_name
            if not terminal_project:
                job_data = job_store.get(job_id)
                terminal_project = job_data.get("project_name", "") if job_data else ""
            if terminal_project:
                try:
                    job_store.clear_project_active_job(terminal_project)
                except Exception:
                    pass
                try:
                    meta_key = GraphSnapshotKeys.meta(terminal_project)
                    meta = sync_get_json(job_store.redis, meta_key) or default_meta()
                    meta.update(
                        {
                            "is_rebuilding": False,
                            "last_refresh_status": "ok" if final_status == "completed" else "failed",
                            "last_error": error if final_status == "failed" else None,
                            "updated_at": now_iso(),
                        }
                    )
                    sync_set_json(job_store.redis, meta_key, meta)
                except Exception as e:
                    logger.warning(f"update snapshot meta on terminal status failed: {e}")

    def ingest_scip_file(
        self,
        scip_file_path: Path,
        project_name: str,
        strict_mode: bool = False,
        source_root: Optional[Path] = None,
        job_id: Optional[str] = None,
    ) -> MappingResult:
        """摄取 SCIP 文件到 Memgraph，支持可选源码路径

        Args:
            scip_file_path: SCIP 文件路径
            project_name: 项目名称
            strict_mode: 严格模式
            source_root: 可选的源码根目录（用于代码提取）
            job_id: 可选的任务ID（用于状态更新）

        Returns:
            MappingResult: 映射结果和统计信息
        """
        logger.info(f"开始摄取 SCIP 文件: {scip_file_path} (source_root={source_root})")

        if job_id:
            self._update_job_status(
                job_id, "parsing", 0, "准备写入任务...", project_name=project_name, write_phase="prepare"
            )

        self._ensure_graph_indexes()
        if job_id:
            self._update_job_status(
                job_id,
                "inserting",
                5,
                "正在清理项目历史数据...",
                project_name=project_name,
                write_phase="clear",
            )
        if self.full_rebuild_only and self.full_rebuild_clear_all:
            logger.warning("full rebuild fast mode enabled: clearing whole graph")
            self.clear_all_graph_data()
        else:
            self.clear_project_data(project_name)

        # 1. 解析 SCIP 文件
        logger.info("步骤 1/4: 解析 SCIP 文件...")
        parser = SCIPParser()
        index = parser.parse_file(str(scip_file_path))
        logger.info(f"解析完成: {len(index.documents)} 个文档")

        if job_id:
            self._update_job_status(job_id, "parsing", 15, f"解析完成: {len(index.documents)} 个文档", project_name=project_name)

        # 2. 映射为图结构
        if job_id:
            self._update_job_status(job_id, "mapping", 20, "正在映射为图结构...", project_name=project_name)
        logger.info("步骤 2/4: 映射为图结构...")
        mapper = SCIPToGraphMapper(
            project_name=project_name,
            strict_mode=strict_mode,
            source_root=source_root,
        )
        result = mapper.map_index(index)
        result = self._deduplicate_mapping_result(result)
        logger.info(
            f"映射完成: {result.stats['total_nodes']} 节点, {result.stats['total_edges']} 边"
        )

        if job_id:
            self._update_job_status(
                job_id, "mapping", 40,
                f"映射完成: {result.stats['total_nodes']} 节点, {result.stats['total_edges']} 边",
                project_name=project_name,
            )

        # 3. 插入节点
        if job_id:
            self._update_job_status(
                job_id,
                "inserting",
                50,
                "正在插入节点...",
                project_name=project_name,
                write_phase="insert_nodes",
                items_total=len(result.nodes),
                items_done=0,
            )
        logger.info("步骤 3/6: 插入节点...")
        self._insert_nodes(
            result.nodes,
            job_id=job_id,
            project_name=project_name,
        )

        # 4. 生成边快照
        if job_id:
            self._update_job_status(
                job_id,
                "inserting",
                68,
                "正在生成边快照...",
                project_name=project_name,
                write_phase="snapshot",
                items_total=len(result.edges),
                items_done=0,
            )
        logger.info("步骤 4/6: 生成边快照...")
        edge_csv_files = self._write_edge_snapshot(result.nodes, result.edges, project_name)
        snapshot_run_dir = edge_csv_files[0].parent if edge_csv_files else None

        try:
            # 5. 批量导入边
            if job_id:
                self._update_job_status(
                    job_id,
                    "inserting",
                    73,
                    "正在批量导入边...",
                    project_name=project_name,
                    write_phase="bulk_load",
                    items_total=len(result.edges),
                    items_done=0,
                )
            logger.info("步骤 5/6: 批量导入边...")
            imported_edges = self._bulk_insert_edges(
                edge_csv_files,
                total_edges=len(result.edges),
                job_id=job_id,
                project_name=project_name,
            )

            # 6. 校验边数量
            if job_id:
                self._update_job_status(
                    job_id,
                    "inserting",
                    78,
                    "正在校验边导入结果...",
                    project_name=project_name,
                    write_phase="verify",
                    items_total=len(result.edges),
                    items_done=imported_edges,
                )
            if self.full_rebuild_verify_edges:
                logger.info("步骤 6/6: 校验边导入...")
                self._verify_edges(project_name, len(result.edges))
            else:
                logger.info("步骤 6/6: 跳过边数量校验（full rebuild fast mode）")
            logger.info("图数据导入完成")
        finally:
            if snapshot_run_dir:
                self._cleanup_snapshot_dir(snapshot_run_dir)

        # 7. 向量化阶段
        if job_id:
            self._update_job_status(
                job_id,
                "vectorizing",
                80,
                "正在生成向量嵌入...",
                project_name=project_name,
                write_phase="vectorizing",
            )
        logger.info("步骤 4/4: 向量化...")
        self._vectorize_nodes(result.nodes, project_name, job_id=job_id)

        if job_id:
            self._update_job_status(
                job_id,
                "completed",
                100,
                "摄取完成",
                project_name=project_name,
                write_phase="completed",
            )

        return result

    def _insert_nodes(
        self,
        nodes,
        job_id: str = None,
        project_name: str = None,
    ):
        """批量插入节点（使用UNWIND优化）"""
        total = len(nodes)
        logger.info(f"插入 {total} 个节点...")

        node_dicts = [
            {
                "id": node.id,
                "label": node.label.value,
                "properties": {
                    k: json.dumps(v) if isinstance(v, (list, dict)) else v
                    for k, v in node.properties.items()
                },
            }
            for node in nodes
        ]

        total_created = 0
        step = min(self.batch_size, 1000)
        for i in range(0, len(node_dicts), step):
            batch = node_dicts[i:i + step]
            self.graph_client.batch_create_nodes(
                batch,
                batch_size=len(batch),
                merge=False,
            )
            total_created += len(batch)
            if job_id and total > 0:
                pct = 50 + int(15 * total_created / total)
                self._update_job_status(
                    job_id, "inserting", pct,
                    f"正在插入节点 {total_created}/{total}...",
                    project_name=project_name,
                    write_phase="insert_nodes",
                    items_total=total,
                    items_done=total_created,
                )

        logger.info(f"节点插入完成: {total_created} 个")

    def _write_edge_snapshot(
        self,
        nodes,
        edges,
        project_name: str,
    ) -> list[Path]:
        """按 (type, from_label, to_label) 分片写边快照 CSV。"""
        total = len(edges)
        logger.info(
            f"写入 {total} 条边到快照文件... chunk_rows={self.bulk_chunk_rows}"
        )

        from collections import defaultdict

        id_to_label = {n.id: n.label.value for n in nodes}
        by_group = defaultdict(list)
        for edge in edges:
            from_label = id_to_label.get(edge.from_id, "")
            to_label = id_to_label.get(edge.to_id, "")
            if not from_label or not to_label:
                continue
            by_group[(edge.type.value, from_label, to_label)].append(edge)

        run_id = uuid.uuid4().hex
        out_dir = self.snapshot_dir / project_name / run_id
        out_dir.mkdir(parents=True, exist_ok=True)

        csv_files: list[Path] = []
        chunk_size = max(1, int(self.bulk_chunk_rows))
        for (edge_type, from_label, to_label), group_edges in by_group.items():
            base_name = f"edges__{edge_type}__{from_label}__{to_label}"
            group_total = len(group_edges)
            parts = (group_total + chunk_size - 1) // chunk_size
            logger.info(
                f"edge group snapshot: type={edge_type} {from_label}->{to_label} "
                f"rows={group_total} parts={parts}"
            )

            for part_idx in range(parts):
                start = part_idx * chunk_size
                end = min(start + chunk_size, group_total)
                chunk_edges = group_edges[start:end]
                if parts == 1:
                    filename = f"{base_name}.csv"
                else:
                    filename = f"{base_name}__part_{part_idx + 1:05d}.csv"

                file_path = out_dir / filename
                with file_path.open("w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(
                        f,
                        fieldnames=["from_id", "to_id", "is_direct", "ref_count"],
                    )
                    writer.writeheader()
                    for edge in chunk_edges:
                        writer.writerow(
                            {
                                "from_id": edge.from_id,
                                "to_id": edge.to_id,
                                "is_direct": "true"
                                if edge.properties.get("is_direct") is True
                                else "",
                                "ref_count": str(edge.properties["count"])
                                if "count" in edge.properties
                                else "",
                            }
                        )
                csv_files.append(file_path)

        logger.info(f"边快照生成完成: {len(csv_files)} 个文件")
        return csv_files

    def _bulk_insert_edges(
        self,
        edge_csv_files: list[Path],
        total_edges: int,
        job_id: str | None = None,
        project_name: str | None = None,
    ) -> int:
        """通过 LOAD CSV 批量导入边。"""
        def _on_file_loaded(imported_total: int, _file_rows: int, _done: int, _all: int) -> None:
            if not job_id or total_edges <= 0:
                return
            clamped = min(imported_total, total_edges)
            pct = 73 + int(5 * clamped / total_edges)
            self._update_job_status(
                job_id,
                "inserting",
                pct,
                f"正在批量导入边 {clamped}/{total_edges}...",
                project_name=project_name,
                write_phase="bulk_load",
                items_total=total_edges,
                items_done=clamped,
            )

        imported = self.bulk_loader.load_edges_with_progress(
            edge_csv_files,
            on_file_loaded=_on_file_loaded,
        )
        logger.info(f"边批量导入完成: {imported} 条")
        return imported

    def _verify_edges(self, project_name: str, expected_edges: int) -> None:
        """校验导入后的边数量。"""
        rows = self.graph_client.execute_query(
            """
            MATCH (n)-[r]->()
            WHERE n.project_id = $project_name
            RETURN count(r) AS total
            """,
            {"project_name": project_name},
        )
        actual_edges = int(rows[0]["total"]) if rows else 0
        if actual_edges != expected_edges:
            raise RuntimeError(
                f"边数量校验失败: expected={expected_edges}, actual={actual_edges}"
            )

    @staticmethod
    def _cleanup_snapshot_dir(snapshot_run_dir: Path) -> None:
        """清理单次导入生成的边快照目录，避免磁盘持续增长。"""
        try:
            shutil.rmtree(snapshot_run_dir)
            logger.info(f"snapshot directory cleaned: {snapshot_run_dir}")
        except FileNotFoundError:
            return
        except Exception as e:
            logger.warning(f"failed to clean snapshot directory {snapshot_run_dir}: {e}")

    def _vectorize_nodes(self, nodes, project_name: str, job_id: str = None):
        """为节点生成向量嵌入并存入 VectorStore"""
        import asyncio
        import hashlib
        import numpy as np
        from src.rag.vector_store import EmbeddingGenerator, VectorStore
        from src.backend.config import get_settings

        settings = get_settings()
        core_labels = {"Function", "Method", "Class", "Interface", "TypeAlias"}
        max_sig_len = 800
        max_doc_len = 1200

        # 构建文本和 ID 列表（只对有意义的符号节点生成嵌入）
        unique_texts: list[str] = []
        ids: list[str] = []
        metas: list[dict] = []
        node_text_hashes: list[str] = []
        seen_text_hashes: set[str] = set()
        for node in nodes:
            label_value = getattr(node.label, "value", str(node.label))
            if label_value not in core_labels:
                continue

            name = node.properties.get("name", "")
            doc = node.properties.get("documentation", "")
            sig = node.properties.get("signature", "")
            kind = node.properties.get("kind", "")
            path = node.properties.get("file_path", node.properties.get("path", ""))
            if isinstance(sig, str) and len(sig) > max_sig_len:
                sig = sig[:max_sig_len]
            if isinstance(doc, str) and len(doc) > max_doc_len:
                doc = doc[:max_doc_len]

            text = f"{kind}: {name}"
            if sig:
                text += f"\n{sig}"
            if doc:
                text += f"\n{doc}"
            if path:
                text += f"\nFile: {path}"

            if not name:
                continue

            text_hash = hashlib.sha1(text.encode("utf-8")).hexdigest()
            if text_hash not in seen_text_hashes:
                seen_text_hashes.add(text_hash)
                unique_texts.append(text)
            ids.append(node.id)
            node_text_hashes.append(text_hash)
            metas.append({"text": text, "name": name, "kind": kind, "project": project_name, "path": path, "label": label_value})

        if not unique_texts:
            logger.info("无可向量化的节点")
            return

        logger.info(f"向量化 {len(ids)} 个节点（去重后 {len(unique_texts)} 条文本）...")

        try:
            generator = EmbeddingGenerator(model=settings.embedding_model)
            store = VectorStore(dimension=generator.dimension)

            # 并发生成嵌入（最多 5 个并发，避免触发 rate limit）
            batch_size = generator.MAX_INPUT_BATCH_SIZE
            async def _run_all():
                sem = asyncio.Semaphore(5)
                async def one(idx, batch):
                    async with sem:
                        result = await generator.generate(batch)
                        return idx, result
                batches = [unique_texts[i:i+batch_size] for i in range(0, len(unique_texts), batch_size)]
                indexed_results: list[list[list[float]] | None] = [None] * len(batches)
                done = 0
                tasks = [asyncio.create_task(one(i, b)) for i, b in enumerate(batches)]
                for fut in asyncio.as_completed(tasks):
                    idx, result = await fut
                    indexed_results[idx] = result
                    done += len(result)
                    if job_id:
                        pct = 80 + int(18 * done / len(unique_texts))
                        self._update_job_status(
                            job_id, "vectorizing", pct,
                            f"正在生成向量嵌入 {done}/{len(unique_texts)}...",
                            project_name=project_name,
                            write_phase="vectorizing",
                            items_total=len(unique_texts),
                            items_done=done,
                        )
                ordered: list[list[float]] = []
                for item in indexed_results:
                    if item:
                        ordered.extend(item)
                return ordered

            unique_embeddings = asyncio.run(_run_all())
            if len(unique_embeddings) != len(unique_texts):
                raise RuntimeError("嵌入数量与文本数量不一致")

            embedding_by_hash = {}
            for text, emb in zip(unique_texts, unique_embeddings):
                h = hashlib.sha1(text.encode("utf-8")).hexdigest()
                embedding_by_hash[h] = emb
            all_embeddings = [embedding_by_hash[h] for h in node_text_hashes]

            if job_id:
                self._update_job_status(
                    job_id, "vectorizing", 98,
                    f"向量嵌入生成完成 {len(unique_embeddings)}/{len(unique_texts)}...",
                    project_name=project_name,
                    write_phase="vectorizing",
                    items_total=len(unique_texts),
                    items_done=len(unique_embeddings),
                )

            vectors = np.array(all_embeddings, dtype='float32')
            store.add(vectors, ids, metas)

            # 持久化到磁盘
            store_path = self.work_dir / f"{project_name}.faiss"
            store.save(str(store_path))
            logger.info(f"向量化完成: {len(ids)} 个向量, 保存到 {store_path}")

        except Exception as e:
            logger.warning(f"向量化失败 (非致命): {e}")

    def clear_project_data(self, project_name: str):
        """清除项目数据

        Args:
            project_name: 项目名称
        """
        logger.warning(f"清除项目数据: {project_name}")
        # 第一步：删除所有属于该项目的非 Project 节点（按属性匹配，避免无界路径遍历）
        self.graph_client.execute_write("""
            MATCH (n)
            WHERE n.project_id = $project_name AND NOT n:Project
            DETACH DELETE n
        """, {"project_name": project_name})
        # 第二步：删除 Project 节点本身
        self.graph_client.execute_write("""
            MATCH (p:Project {id: $project_id})
            DETACH DELETE p
        """, {"project_id": f"project:{project_name}"})
        logger.info("项目数据已清除")

    def clear_all_graph_data(self):
        """清空整个图数据（全量重建极速模式）。"""
        logger.warning("清空整个图数据库...")
        self.graph_client.execute_write("MATCH (n) DETACH DELETE n")
        logger.info("整库图数据已清空")
