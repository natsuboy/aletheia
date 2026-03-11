"""源码提供者 - 支持多种源码获取方式

支持三种源码提供方式：
1. LocalPathProvider - 本地文件系统路径
2. ZipFileProvider - ZIP 压缩文件
3. GitLabRepoProvider - GitLab 仓库克隆
"""
import asyncio
import shutil
import zipfile
from pathlib import Path
from typing import Optional, List
from abc import ABC, abstractmethod
from loguru import logger


class SourceProvider(ABC):
    """源码提供者基类"""

    @abstractmethod
    def is_available(self) -> bool:
        """检查源码是否可用"""
        pass

    @abstractmethod
    def get_file(self, relative_path: str) -> str:
        """获取文件内容

        Args:
            relative_path: 相对路径

        Returns:
            文件内容

        Raises:
            FileNotFoundError: 文件不存在
        """
        pass

    @abstractmethod
    def list_files(self) -> List[str]:
        """列出所有文件

        Returns:
            文件路径列表
        """
        pass


class LocalPathProvider(SourceProvider):
    """本地路径源码提供者"""

    def __init__(self, root_path: str):
        """
        Args:
            root_path: 源码根目录路径
        """
        self.root_path = Path(root_path).resolve()

    def is_available(self) -> bool:
        """检查目录是否存在"""
        return self.root_path.is_dir()

    def get_file(self, relative_path: str) -> str:
        """获取文件内容"""
        file_path = self.root_path / relative_path

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {relative_path}")

        return file_path.read_text(encoding='utf-8')

    def list_files(self) -> List[str]:
        """列出所有文件"""
        files = []
        for file_path in self.root_path.rglob('*'):
            if file_path.is_file():
                # 返回相对于 root_path 的路径
                relative = file_path.relative_to(self.root_path)
                files.append(str(relative))
        return files


class ZipFileProvider(SourceProvider):
    """ZIP 文件源码提供者"""

    def __init__(self, zip_path: str):
        """
        Args:
            zip_path: ZIP 文件路径
        """
        self.zip_path = Path(zip_path).resolve()
        self._zip_file: Optional[zipfile.ZipFile] = None

    def is_available(self) -> bool:
        """检查 ZIP 文件是否存在"""
        return self.zip_path.is_file()

    def _open_zip(self):
        """打开 ZIP 文件"""
        if self._zip_file is None:
            self._zip_file = zipfile.ZipFile(self.zip_path, 'r')
        return self._zip_file

    def get_file(self, relative_path: str) -> str:
        """从 ZIP 获取文件内容"""
        zip_file = self._open_zip()

        try:
            # ZIP 中使用正斜杠
            normalized_path = relative_path.replace('\\', '/')
            with zip_file.open(normalized_path) as f:
                return f.read().decode('utf-8')
        except KeyError:
            raise FileNotFoundError(f"File not found in ZIP: {relative_path}")

    def list_files(self) -> List[str]:
        """列出 ZIP 中的所有文件"""
        zip_file = self._open_zip()
        return [name for name in zip_file.namelist() if not name.endswith('/')]

    def close(self):
        """关闭 ZIP 文件"""
        if self._zip_file:
            self._zip_file.close()
            self._zip_file = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class GitLabRepoProvider(SourceProvider):
    """GitLab 仓库源码提供者"""

    def __init__(
        self,
        repo_url: str,
        branch: str = "main",
        token: Optional[str] = None,
        work_dir: str = "/tmp/aletheia"
    ):
        """
        Args:
            repo_url: GitLab 仓库 URL
            branch: 分支名称
            token: GitLab 访问 Token（私有仓库需要）
            work_dir: 工作目录
        """
        self.repo_url = repo_url
        self.branch = branch
        self.token = token
        self.work_dir = Path(work_dir)
        self._cloned_path: Optional[Path] = None

    async def clone(self) -> Path:
        """克隆 GitLab 仓库

        Returns:
            克隆后的目录路径
        """
        self.work_dir.mkdir(parents=True, exist_ok=True)

        # 从 URL 提取项目名
        project_name = self.repo_url.rstrip('.git').split('/')[-1]
        target_path = self.work_dir / project_name

        # 如果目录已存在，先删除
        if target_path.exists():
            logger.info(f"Removing existing directory: {target_path}")
            shutil.rmtree(target_path)

        # 构建克隆命令
        cmd = ["git", "clone", "--depth", "1", "--branch", self.branch, self.repo_url, str(target_path)]

        # 添加认证（如果提供了 token）
        if self.token:
            # 修改 URL 以包含 token
            if self.repo_url.startswith('https://'):
                auth_url = self.repo_url.replace('https://', f'https://oauth2:{self.token}@')
                cmd[3] = auth_url

        logger.info(f"Cloning {self.repo_url} to {target_path}")

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = f"Git clone failed: {stderr.decode()}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        self._cloned_path = target_path
        return target_path

    def is_available(self) -> bool:
        """检查是否已克隆"""
        return self._cloned_path is not None and self._cloned_path.exists()

    def get_file(self, relative_path: str) -> str:
        """获取文件内容"""
        if not self.is_available():
            raise RuntimeError("Repository not cloned. Call clone() first.")

        file_path = self._cloned_path / relative_path

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {relative_path}")

        return file_path.read_text(encoding='utf-8')

    def list_files(self) -> List[str]:
        """列出所有文件"""
        if not self.is_available():
            raise RuntimeError("Repository not cloned. Call clone() first.")

        files = []
        for file_path in self._cloned_path.rglob('*'):
            if file_path.is_file():
                relative = file_path.relative_to(self._cloned_path)
                files.append(str(relative))
        return files

    def cleanup(self):
        """清理克隆的目录"""
        if self._cloned_path and self._cloned_path.exists():
            logger.info(f"Cleaning up cloned repository: {self._cloned_path}")
            shutil.rmtree(self._cloned_path)
            self._cloned_path = None


class SourceProviderFactory:
    """源码提供者工厂"""

    @staticmethod
    def create(source_type: str, config: dict) -> SourceProvider:
        """创建源码提供者

        Args:
            source_type: 源码类型 (local_path, zip_file, gitlab_repo)
            config: 配置字典

        Returns:
            源码提供者实例

        Raises:
            ValueError: 无效的源码类型
        """
        if source_type == "local_path":
            path = (
                config.get("path")
                or config.get("local_source_path")
                or config.get("root_path")
            )
            if not path:
                raise ValueError("local_path source requires 'path' or 'local_source_path'")
            return LocalPathProvider(
                root_path=path
            )

        elif source_type == "zip_file":
            zip_path = config.get("zip_path") or config.get("source_zip_path")
            if not zip_path:
                raise ValueError("zip_file source requires 'zip_path' or 'source_zip_path'")
            return ZipFileProvider(
                zip_path=zip_path
            )

        elif source_type == "gitlab_repo":
            repo_url = config.get("repo_url") or config.get("gitlab_repo")
            if not repo_url:
                raise ValueError("gitlab_repo source requires 'repo_url' or 'gitlab_repo'")
            return GitLabRepoProvider(
                repo_url=repo_url,
                branch=config.get("branch", config.get("gitlab_branch", "main")),
                token=config.get("token", config.get("gitlab_token")),
                work_dir=config.get("work_dir", "/tmp/aletheia")
            )

        else:
            raise ValueError(f"Unknown source type: {source_type}")
