"""
若茗 PaaS - 文件中心 Schema
"""
from datetime import datetime

from pydantic import BaseModel, Field


class FileInfo(BaseModel):
    """文件信息"""

    id: int
    original_name: str
    file_name: str
    file_ext: str | None
    mime_type: str | None
    file_size: int
    file_hash: str
    storage_backend: str
    storage_key: str
    storage_url: str | None
    biz_type: str | None
    biz_id: str | None
    category: str | None
    remark: str | None
    uploader_id: int | None
    download_count: int
    is_public: bool
    status: int
    archived_at: datetime | None
    archived_by: int | None
    archive_reason: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FileArchiveRequest(BaseModel):
    """归档文件请求"""

    reason: str | None = Field(None, max_length=500, description="归档原因")


class FileUpdateRequest(BaseModel):
    """更新文件元信息"""

    biz_type: str | None = Field(None, max_length=64)
    biz_id: str | None = Field(None, max_length=64)
    category: str | None = Field(None, max_length=64)
    remark: str | None = Field(None, max_length=255)
    is_public: bool | None = None


class StorageConfigInfo(BaseModel):
    """当前存储配置摘要"""

    backend: str
    upload_dir: str | None = None
    max_upload_size_mb: int
    allowed_extensions: list[str]
    supports: list[str]
