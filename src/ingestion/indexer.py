"""SCIP 索引器管理"""

import subprocess
from pathlib import Path
from typing import Optional

from loguru import logger

from src.backend.config import get_settings


class IndexerManager:
    """SCIP 索引器管理器"""

    SUPPORTED_LANGUAGES = {"go", "python", "typescript"}

    def __init__(self):
        self._settings = get_settings()

    def is_language_supported(self, language: str) -> bool:
        """检查语言是否支持"""
        return language.lower() in self.SUPPORTED_LANGUAGES

    def index_project(
        self, project_path: Path, language: str, output_path: Optional[Path] = None
    ) -> Path:
        """为项目生成 SCIP 索引

        Args:
            project_path: 项目根目录路径
            language: 编程语言 (当前仅支持 'go')
            output_path: 输出文件路径 (默认为 project_path/index.scip)

        Returns:
            生成的 SCIP 索引文件路径

        Raises:
            ValueError: 不支持的语言
            RuntimeError: 索引生成失败
        """
        if not self.is_language_supported(language):
            raise ValueError(
                f"Language '{language}' is not supported. "
                f"Supported languages: {', '.join(self.SUPPORTED_LANGUAGES)}"
            )

        if not project_path.exists():
            raise FileNotFoundError(f"Project path does not exist: {project_path}")

        # 确定输出路径
        if output_path is None:
            output_path = project_path / "index.scip"

        # 根据语言调用对应的索引器
        if language.lower() == "go":
            return self._index_go_project(project_path, output_path)
        elif language.lower() == "python":
            return self._index_python_project(project_path, output_path)
        elif language.lower() == "typescript":
            return self._index_typescript_project(project_path, output_path)
        raise NotImplementedError(f"Indexer for '{language}' is not implemented")

    def _index_go_project(self, project_path: Path, output_path: Path) -> Path:
        """为 Go 项目生成 SCIP 索引"""
        indexer_path = self._settings.scip_go_path

        # 检查 scip-go 是否存在
        if not Path(indexer_path).exists():
            logger.warning(f"scip-go not found at {indexer_path}, attempting to use from PATH")
            indexer_path = "scip-go"

        logger.info(f"Indexing Go project at {project_path}")

        # List files for debugging
        try:
            files = subprocess.check_output(["ls", "-R"], cwd=project_path, text=True)
            logger.debug(f"Files in project: \n{files[:1000]}...")  # Truncate log
        except Exception as e:
            logger.error(f"Failed to list files: {e}")

        try:
            # Check if go.mod exists
            if (project_path / "go.mod").exists():
                logger.info("Found go.mod, running go mod download...")
                subprocess.run(["go", "mod", "download"], cwd=project_path, check=False)

            # 执行 scip-go index
            result = subprocess.run(
                [indexer_path, "index", "--output", str(output_path)],
                cwd=project_path,
                capture_output=True,
                text=True,
                check=True,
            )

            logger.info(f"Successfully generated SCIP index at {output_path}")
            logger.debug(f"scip-go output: {result.stdout}")

            return output_path

        except subprocess.CalledProcessError as e:
            error_msg = f"Failed to index Go project: {e.stderr}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

        except FileNotFoundError:
            error_msg = "scip-go not found. Please install it and set SCIP_GO_PATH in .env"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

    def _index_python_project(self, project_path: Path, output_path: Path) -> Path:
        """为 Python 项目生成 SCIP 索引"""
        indexer_path = self._settings.scip_python_path
        if not Path(indexer_path).exists():
            indexer_path = "scip-python"
        logger.info(f"Indexing Python project at {project_path}")
        try:
            result = subprocess.run(
                [indexer_path, "index", ".", "--output", str(output_path)],
                cwd=project_path, capture_output=True, text=True, check=True,
            )
            logger.info(f"Successfully generated SCIP index at {output_path}")
            return output_path
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to index Python project: {e.stderr}") from e
        except FileNotFoundError:
            raise RuntimeError("scip-python not found. Please install it and set SCIP_PYTHON_PATH in .env")

    def _index_typescript_project(self, project_path: Path, output_path: Path) -> Path:
        """为 TypeScript 项目生成 SCIP 索引"""
        indexer_path = self._settings.scip_typescript_path
        if not Path(indexer_path).exists():
            indexer_path = "scip-typescript"
        logger.info(f"Indexing TypeScript project at {project_path}")
        try:
            result = subprocess.run(
                [indexer_path, "index", "--output", str(output_path)],
                cwd=project_path, capture_output=True, text=True, check=True,
            )
            logger.info(f"Successfully generated SCIP index at {output_path}")
            return output_path
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to index TypeScript project: {e.stderr}") from e
        except FileNotFoundError:
            raise RuntimeError("scip-typescript not found. Please install it and set SCIP_TYPESCRIPT_PATH in .env")

    def validate_scip_file(self, scip_path: Path) -> bool:
        """验证 SCIP 文件是否有效

        Args:
            scip_path: SCIP 文件路径

        Returns:
            文件是否有效
        """
        if not scip_path.exists():
            logger.error(f"SCIP file does not exist: {scip_path}")
            return False

        if scip_path.stat().st_size == 0:
            logger.error(f"SCIP file is empty: {scip_path}")
            return False

        # 检查文件大小限制
        max_size_mb = self._settings.max_file_size_mb
        size_mb = scip_path.stat().st_size / (1024 * 1024)
        if size_mb > max_size_mb:
            logger.warning(f"SCIP file is large ({size_mb:.2f} MB), may take time to process")

        logger.info(f"SCIP file validated: {scip_path} ({size_mb:.2f} MB)")
        return True
