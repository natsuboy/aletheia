"""应用配置管理"""
import os
from functools import lru_cache
from typing import List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置"""

    # 应用配置
    app_name: str = "Aletheia"
    app_env: str = Field(default="development", description="Application environment")
    debug: bool = Field(default=False, description="Debug mode")
    log_level: str = Field(default="INFO", description="Logging level")

    # 数据库配置
    memgraph_host: str = Field(default="localhost", description="Memgraph host")
    memgraph_port: int = Field(default=7687, description="Memgraph port")
    memgraph_username: str = Field(default="", description="Memgraph username")
    memgraph_password: str = Field(default="", description="Memgraph password")

    # Redis 配置
    redis_host: str = Field(default="localhost", description="Redis host")
    redis_port: int = Field(default=6379, description="Redis port")
    redis_db: int = Field(default=0, description="Redis database number")

    # LLM API 密钥（敏感信息必须来自环境变量）
    openai_api_key: str = Field(default="", description="OpenAI API key")
    openai_base_url: str = Field(default="", description="Custom OpenAI base URL")
    embedding_api_key: str = Field(default="", description="Embedding model API key")
    embedding_base_url: str = Field(default="", description="Embedding model base URL")
    google_api_key: str = Field(default="", description="Google API key")
    anthropic_api_key: str = Field(default="", description="Anthropic API key")

    # 摄取配置
    scip_go_path: str = Field(default="/usr/local/bin/scip-go", description="Path to scip-go binary")
    scip_python_path: str = Field(default="/usr/local/bin/scip-python", description="Path to scip-python binary")
    scip_typescript_path: str = Field(default="/usr/local/bin/scip-typescript", description="Path to scip-typescript binary")
    max_file_size_mb: int = Field(default=10, description="Maximum file size in MB")
    batch_size: int = Field(default=1000, description="Batch size for processing")
    csv_staging_write_dir: str = Field(
        default="/data/ingest_snapshots",
        description="CSV staging directory for worker writes",
    )
    csv_staging_read_dir: str = Field(
        default="/data/ingest_snapshots",
        description="CSV staging directory as seen by Memgraph",
    )
    bulk_chunk_rows: int = Field(default=200000, description="Rows per bulk csv chunk")
    bulk_load_timeout_seconds: int = Field(
        default=120, description="Timeout seconds for each LOAD CSV write transaction"
    )
    full_rebuild_only: bool = Field(
        default=True,
        description="Always perform full rebuild ingestion and skip incremental commit checks",
    )
    full_rebuild_clear_all: bool = Field(
        default=True,
        description="When full rebuild is enabled, clear whole graph before importing",
    )
    full_rebuild_verify_edges: bool = Field(
        default=False,
        description="Whether to verify edge count after bulk import in full rebuild mode",
    )

    # RAG 配置
    default_llm_model: str = Field(default="gpt-4", description="Default LLM model")
    embedding_model: str = Field(default="text-embedding-3-small", description="Embedding model")
    max_context_tokens: int = Field(default=8000, description="Maximum context tokens")
    vector_search_k: int = Field(default=10, description="Vector search K value")

    # 安全配置
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:5173",
        description="CORS allowed origins (comma-separated)"
    )
    jwt_secret: str = Field(
        default="",
        description="JWT secret key (must be set in production)"
    )
    rate_limit_per_minute: int = Field(default=60, description="Rate limit per minute")

    # Wiki 配置
    wiki_max_pages: int = Field(default=50, description="Wiki max pages per project")
    wiki_cache_ttl: int = Field(default=86400, description="Wiki cache TTL in seconds")

    # 会话配置
    conversation_ttl: int = Field(default=3600, description="Conversation TTL in seconds")
    conversation_max_turns: int = Field(default=20, description="Max conversation turns")

    # Research 配置
    research_max_iterations: int = Field(default=5, description="Max research iterations")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @field_validator("jwt_secret")
    @classmethod
    def validate_jwt_secret(cls, v: str, info) -> str:
        """验证JWT密钥"""
        app_env = info.data.get("app_env", "development")

        if app_env == "production":
            if not v:
                raise ValueError("JWT_SECRET must be set in production")
            if len(v) < 32:
                raise ValueError("JWT_SECRET must be at least 32 characters in production")
            if v == "your-secret-key-change-in-production":
                raise ValueError("JWT_SECRET must be changed from default value")

        return v

    @field_validator("cors_origins")
    @classmethod
    def parse_cors_origins(cls, v: str) -> str:
        """解析并验证CORS源"""
        if not v:
            return ""

        origins = [origin.strip() for origin in v.split(",")]

        # 验证每个origin的格式
        for origin in origins:
            if origin == "*":
                continue
            if not (origin.startswith("http://") or origin.startswith("https://")):
                raise ValueError(f"Invalid CORS origin: {origin}")

        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """验证日志级别"""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v.upper()

    @property
    def cors_origins_list(self) -> List[str]:
        """获取CORS源列表"""
        if not self.cors_origins:
            return []
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def is_production(self) -> bool:
        """是否为生产环境"""
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        """是否为开发环境"""
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()
