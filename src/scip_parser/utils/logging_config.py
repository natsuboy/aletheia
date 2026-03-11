"""
日志配置模块

为 SCIP Parser 提供统一的日志配置和工具函数。
"""

from __future__ import annotations

import logging
import os
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from logging import Logger


_loggers: dict[str, Logger] = {}


def _is_running_in_pytest() -> bool:
    """检测是否在 pytest 环境中运行"""
    return "PYTEST_CURRENT_TEST" in os.environ or "pytest" in sys.modules


def get_logger(name: str) -> Logger:
    """获取或创建指定名称的 Logger

    Args:
        name: Logger 名称

    Returns:
        Logger 实例
    """
    if name not in _loggers:
        _loggers[name] = logging.getLogger(name)
    return _loggers[name]


def setup_logging(
    level: int = logging.WARNING,
    log_file: str | None = None,
    format_string: str | None = None,
) -> None:
    """配置日志系统

    Args:
        level: 日志级别 (默认 WARNING)
        log_file: 可选的日志文件路径
        format_string: 自定义格式字符串
    """
    if format_string is None:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # 配置根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # 清除现有处理器
    root_logger.handlers.clear()

    # 创建控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter(format_string))
    root_logger.addHandler(console_handler)

    # 如果指定了日志文件,创建文件处理器
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(format_string))
        root_logger.addHandler(file_handler)


def enable_debug_logging() -> None:
    """启用 DEBUG 级别日志

    这将输出所有模块的详细调试信息。

    在 pytest 中运行时,需要添加 --log-cli-level=DEBUG 参数才能看到输出。
    或者使用 enable_pytest_debug_logging() 来自动配置 pytest 的日志输出。
    """
    if _is_running_in_pytest():
        import warnings

        warnings.warn(
            "检测到在 pytest 环境中运行。"
            "请在 pytest 命令中添加 --log-cli-level=DEBUG 参数来查看日志输出, "
            "或者使用 enable_pytest_debug_logging() 函数。",
            UserWarning,
            stacklevel=2,
        )
    setup_logging(level=logging.DEBUG)


def enable_pytest_debug_logging() -> None:
    """为 pytest 启用 DEBUG 级别日志

    这个函数专门为 pytest 环境设计,会自动配置 pytest 的日志输出。
    使用后不需要在 pytest 命令中添加 --log-cli-level=DEBUG 参数。

    Example:
        在 conftest.py 中:
        ```python
        import pytest
        from src.scip_parser.utils.logging_config import enable_pytest_debug_logging

        @pytest.fixture(autouse=True)
        def setup_logging():
            enable_pytest_debug_logging()
        ```
    """
    if not _is_running_in_pytest():
        enable_debug_logging()
        return

    # 配置 pytest 的日志输出
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # 设置所有 scip_parser 相关的 logger 为 DEBUG 级别
    for name in list(logging.Logger.manager.loggerDict.keys()):
        if name.startswith("scip_parser"):
            logging.getLogger(name).setLevel(logging.DEBUG)

    # 配置 pytest 的日志捕获
    # 通过设置环境变量来影响 pytest 的日志行为
    os.environ["PYTEST_LOG_LEVEL"] = "DEBUG"


def enable_info_logging() -> None:
    """启用 INFO 级别日志

    这将输出一般信息和警告。

    在 pytest 中运行时,需要添加 --log-cli-level=INFO 参数才能看到输出。
    """
    if _is_running_in_pytest():
        import warnings

        warnings.warn(
            "检测到在 pytest 环境中运行。"
            "请在 pytest 命令中添加 --log-cli-level=INFO 参数来查看日志输出。",
            UserWarning,
            stacklevel=2,
        )
    setup_logging(level=logging.INFO)


def get_parser_logger() -> Logger:
    """获取解析器专用的 Logger"""
    return get_logger("scip_parser.core.parser")


def get_index_logger() -> Logger:
    """获取索引专用的 Logger"""
    return get_logger("scip_parser.core.types")


def get_query_logger() -> Logger:
    """获取查询专用的 Logger"""
    return get_logger("scip_parser.query.api")
