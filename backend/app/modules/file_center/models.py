"""
若茗 PaaS - 文件中心模型
"""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class SysFile(BaseModel):
    """系统文件表（sys_file）"""

    __tablename__ = "sys_file"

    original_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="原始文件名")
    file_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="存储文件名")
    file_ext: Mapped[str] = mapped_column(String(32), nullable=True, index=True, comment="文件扩展名")
    mime_type: Mapped[str] = mapped_column(String(128), nullable=True, comment="MIME 类型")
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="文件大小（字节）")
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True, comment="SHA256 哈希")

    storage_backend: Mapped[str] = mapped_column(String(32), nullable=False, comment="存储后端：local/minio/oss")
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True, comment="存储对象 key")
    storage_url: Mapped[str] = mapped_column(String(1024), nullable=True, comment="存储访问 URL")

    biz_type: Mapped[str] = mapped_column(String(64), nullable=True, index=True, comment="业务类型")
    biz_id: Mapped[str] = mapped_column(String(64), nullable=True, index=True, comment="业务 ID")
    category: Mapped[str] = mapped_column(String(64), nullable=True, index=True, comment="文件分类")
    remark: Mapped[str] = mapped_column(String(255), nullable=True, comment="备注")

    uploader_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True, comment="上传人 ID")
    download_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="下载次数")
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", comment="是否公开")
    status: Mapped[int] = mapped_column(
        SmallInteger,
        default=1,
        server_default="1",
        index=True,
        comment="状态：1正常 2已归档",
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="归档时间")
    archived_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="归档人 ID")
    archive_reason: Mapped[str | None] = mapped_column(Text, nullable=True, comment="归档原因")
