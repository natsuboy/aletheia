"""边关系批量导入器（基于 LOAD CSV）。"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable

from loguru import logger

from src.graph.client import GraphClient
from src.graph.exceptions import GraphTransactionError


class BulkLoader:
    """使用 Memgraph LOAD CSV 批量导入关系边。"""

    def __init__(
        self,
        graph_client: GraphClient,
        write_root: Path,
        read_root: Path,
        load_timeout_seconds: int = 120,
    ):
        self.graph_client = graph_client
        self.write_root = write_root.resolve()
        self.read_root = read_root
        self.load_timeout_seconds = max(1, load_timeout_seconds)

    @staticmethod
    def _escape_cypher_string(value: str) -> str:
        """转义 Cypher 单引号字符串字面量。"""
        return value.replace("\\", "\\\\").replace("'", "\\'")

    def _parse_edge_filename(self, csv_file: Path) -> tuple[str, str, str] | None:
        parts = csv_file.stem.split("__")
        if len(parts) < 4 or parts[0] != "edges":
            return None
        if len(parts) > 4 and not all(p.startswith("part_") for p in parts[4:]):
            return None
        return (
            parts[1],
            parts[2],
            parts[3],
        )

    def _to_csv_path(self, path: Path) -> str:
        try:
            rel = path.resolve().relative_to(self.write_root)
        except ValueError as e:
            raise GraphTransactionError(
                message=f"CSV path escapes staging write root: {path}",
                original_error=e,
            )
        # Memgraph 3.8.0 在当前环境中对 `file://` 形式不兼容，需使用绝对路径。
        return (self.read_root / rel).as_posix()

    def _preflight(self, csv_file: Path) -> str:
        csv_path = self._to_csv_path(csv_file)
        escaped_path = self._escape_cypher_string(csv_path)
        query = f"LOAD CSV FROM '{escaped_path}' WITH HEADER AS row RETURN 1 LIMIT 1"
        try:
            self.graph_client.execute_write_no_retry(query, timeout=self.load_timeout_seconds)
            logger.info(f"LOAD CSV read root verified: {self.read_root}")
        except Exception as e:
            raise GraphTransactionError(
                message=(
                    "LOAD CSV preflight failed. "
                    f"csv_path={csv_path}, write_root={self.write_root}, read_root={self.read_root}. "
                    "请检查 docker-compose 挂载并重建 memgraph 容器。"
                ),
                original_error=e,
            )
        return csv_path

    def load_edges(self, csv_files: Iterable[Path]) -> int:
        """导入边 CSV 文件集合并返回导入总数。"""
        return self.load_edges_with_progress(csv_files)

    def load_edges_with_progress(
        self,
        csv_files: Iterable[Path],
        on_file_loaded: Callable[[int, int, int, int], None] | None = None,
    ) -> int:
        """导入边 CSV 文件集合并返回导入总数，支持按文件回调进度。

        Args:
            csv_files: 待导入 CSV 文件列表
            on_file_loaded: 每个文件完成后的回调，参数依次为
                (imported_total_rows, current_file_rows, files_done, files_total)
        """
        files = list(csv_files)
        total = 0
        preflight_done = False
        files_total = len(files)
        for idx, csv_file in enumerate(files, start=1):
            parsed = self._parse_edge_filename(csv_file)
            if not parsed:
                logger.warning(f"skip malformed edge csv filename: {csv_file.name}")
                continue

            if not preflight_done:
                self._preflight(csv_file)
                preflight_done = True

            edge_type, from_label, to_label = parsed
            csv_path = self._to_csv_path(csv_file)
            escaped_path = self._escape_cypher_string(csv_path)
            query = f"""
            LOAD CSV FROM '{escaped_path}' WITH HEADER AS row
            MATCH (from:{from_label} {{id: row.from_id}})
            MATCH (to:{to_label} {{id: row.to_id}})
            CREATE (from)-[r:{edge_type}]->(to)
            FOREACH (_ IN CASE WHEN row.is_direct = '' THEN [] ELSE [1] END |
              SET r.is_direct = toBoolean(row.is_direct)
            )
            FOREACH (_ IN CASE WHEN row.ref_count = '' THEN [] ELSE [1] END |
              SET r.count = toInteger(row.ref_count)
            )
            """
            try:
                self.graph_client.execute_write_no_retry(query, timeout=self.load_timeout_seconds)
            except Exception as e:
                if "CSV file not found" in str(e):
                    raise GraphTransactionError(
                        message=(
                            "LOAD CSV failed: CSV file not found. "
                            f"csv_path={csv_path}, write_root={self.write_root}, read_root={self.read_root}. "
                            "请执行: docker compose up -d --force-recreate memgraph"
                        ),
                        original_error=e,
                    )
                raise
            with csv_file.open("r", encoding="utf-8") as f:
                rows = sum(1 for _ in f) - 1
            total += max(rows, 0)
            logger.info(f"bulk loaded edges: {csv_file.name} ({rows})")
            if on_file_loaded is not None:
                on_file_loaded(total, max(rows, 0), idx, files_total)
        return total
