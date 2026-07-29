"""
若茗 PaaS - 全局配置
Author: ruoming
"""
import os
from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── 环境标识 ──────────────────────────────────────────────────────
    APP_ENV: Literal["development", "test", "production"] = "development"
    APP_NAME: str = "RuoMing PaaS"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False
    DEMO_MODE: bool = False

    # ── 数据库（必填，启动 Fail-Fast）────────────────────────────────
    DATABASE_URL: str  # postgresql+asyncpg://user:pwd@host:5432/dbname
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_POOL_RECYCLE: int = 3600
    # 只读副本（可选）：配置后自动启用读写分离，不配置则读写同库
    DATABASE_REPLICA_URL: str = ""

    # ── Redis（必填）──────────────────────────────────────────────────
    REDIS_URL: str  # redis://localhost:6379/0
    REDIS_MAX_CONNECTIONS: int = 20
    # 部署模式：standalone（默认）/ sentinel / cluster
    REDIS_MODE: str = "standalone"
    REDIS_SENTINEL_HOSTS: str = "127.0.0.1:26379"  # 逗号分隔：host:port,host:port
    REDIS_SENTINEL_MASTER: str = "mymaster"
    REDIS_SENTINEL_PASSWORD: str = ""
    REDIS_CLUSTER_NODES: str = "127.0.0.1:7000"    # 逗号分隔：host:port,host:port

    # ── 安全（必填）──────────────────────────────────────────────────
    SECRET_KEY: str  # 至少 32 位随机字符串
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15   # 生产建议 15 分钟
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ENCRYPT_KEY: str = ""  # AES-256 加密密钥，32字节base64，留空则自动生成（开发用）

    # ── CORS ──────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    ALLOWED_HOSTS: list[str] = ["*"]

    # ── 登录安全 ──────────────────────────────────────────────────────
    LOGIN_FAIL_MAX_TIMES: int = 5           # 最多失败次数
    LOGIN_LOCK_MINUTES: int = 30            # 锁定时长（分钟）
    BCRYPT_COST_FACTOR: int = 12            # bcrypt 成本因子（4-31），生产建议 12-14

    # ── 限流 ──────────────────────────────────────────────────────────
    RATE_LIMIT_DEFAULT: str = "100/minute"
    RATE_LIMIT_LOGIN: str = "10/minute"
    RATE_LIMIT_AI: str = "30/minute"

    # ── AI 配置 ───────────────────────────────────────────────────────
    AI_DEFAULT_PROVIDER: str = "openai"
    AI_DEFAULT_MODEL: str = "gpt-3.5-turbo"
    AI_DEFAULT_TEMPERATURE: float = 0.7
    AI_DEFAULT_MAX_TOKENS: int = 2048
    AI_REQUEST_TIMEOUT: int = 30

    # 追鹿 API（主力 LLM）
    ZHUILU_API_KEY: str = ""
    ZHUILU_BASE_URL: str = "https://api.zhuilu.ai/v1"
    ZHUILU_DEFAULT_MODEL: str = "deepseek-chat"

    # OpenAI 兼容（备用）
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"

    # Ollama（本地模型，开发用）
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # ── 向量数据库 ───────────────────────────────────────────────────
    VECTOR_STORE_TYPE: str = "pgvector"     # pgvector / milvus / qdrant
    VECTOR_DIMENSION: int = 1536            # Embedding 维度
    EMBEDDING_MODEL: str = "text-embedding-3-small"

    # ── 文件存储 ──────────────────────────────────────────────────────
    STORAGE_BACKEND: str = "local"          # local / oss / minio
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_UPLOAD_EXTENSIONS: list[str] = [
        "jpg", "jpeg", "png", "gif", "webp",
        "pdf", "doc", "docx", "xls", "xlsx", "txt", "md",
        "zip", "rar", "7z",
        "mp4", "mp3",
    ]
    # 阿里云 OSS
    OSS_ENDPOINT: str = ""
    OSS_BUCKET: str = ""
    OSS_ACCESS_KEY: str = ""
    OSS_SECRET_KEY: str = ""
    OSS_CDN_DOMAIN: str = ""

    # MinIO / S3 兼容
    MINIO_ENDPOINT: str = ""
    MINIO_BUCKET: str = ""
    MINIO_ACCESS_KEY: str = ""
    MINIO_SECRET_KEY: str = ""
    MINIO_SECURE: bool = False
    MINIO_CDN_DOMAIN: str = ""

    # ── 任务队列（Celery）───────────────────────────────────────────────
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    WORKER_CONCURRENCY: int = 10

    # ── 监控 ──────────────────────────────────────────────────────────
    PROMETHEUS_ENABLED: bool = True
    PROMETHEUS_PORT: int = 9090

    # ── 日志 ──────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = True                   # 生产环境输出 JSON 日志

    # ── 邮件（可选，用于通知）────────────────────────────────────────
    SMTP_HOST: str = ""
    SMTP_PORT: int = 465
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    SMTP_TLS: bool = True

    model_config = SettingsConfigDict(
        env_file=(
            ".env",
            f".env.{os.getenv('APP_ENV', 'development')}",
        ),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("SECRET_KEY 长度不能少于 32 位，请生成一个强随机密钥")
        return v

    @model_validator(mode="after")
    def set_defaults(self) -> "Settings":
        # 开发环境：若未设置 ENCRYPT_KEY，则自动派生（不安全，仅开发用）
        if not self.ENCRYPT_KEY and self.APP_ENV != "production":
            import hashlib
            derived = hashlib.sha256(self.SECRET_KEY.encode()).hexdigest()[:32]
            object.__setattr__(self, "ENCRYPT_KEY", derived)
        return self

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    @property
    def docs_url(self) -> str | None:
        return None if self.is_production else "/api/docs"

    @property
    def redoc_url(self) -> str | None:
        return None if self.is_production else "/api/redoc"


@lru_cache
def get_settings() -> Settings:
    """单例，整个应用共享同一份 Settings 实例"""
    return Settings()


settings = get_settings()
