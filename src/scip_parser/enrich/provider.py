"""
源码提供者接口
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Optional


class SourceProvider(ABC):
    """源码提供者基类"""

    @abstractmethod
    def get_content(self, relative_path: str) -> Optional[str]:
        """获取文件内容

        Args:
            relative_path: 相对于项目根目录的路径

        Returns:
            文件内容字符串，如果文件不存在或无法读取则返回 None
        """
        pass


class FileSystemSourceProvider(SourceProvider):
    """基于文件系统的源码提供者"""

    def __init__(self, project_root: str):
        self.project_root = project_root

    def get_content(self, relative_path: str) -> Optional[str]:
        full_path = os.path.join(self.project_root, relative_path)
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                return f.read()
        except (OSError, UnicodeDecodeError):
            return None
