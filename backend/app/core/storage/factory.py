"""
存储后端工厂

根据 settings.STORAGE_BACKEND 自动实例化对应的 FileStorage 实现。
"""
from __future__ import annotations

import logging
from functools import lru_cache

from app.config import settings
from app.core.storage.base import FileStorage

logger = logging.getLogger(__name__)


@lru_cache
def get_storage() -> FileStorage:
    """根据配置获取存储实例（单例）"""
    backend = (settings.STORAGE_BACKEND or "local").lower()
    logger.info(f"Initializing file storage backend: {backend}")

    if backend == "local":
        from app.core.storage.local_storage import LocalStorage
        return LocalStorage(
            base_dir=settings.UPLOAD_DIR,
            url_prefix="/static/uploads",
        )

    if backend == "oss":
        from app.core.storage.oss_storage import OSSStorage
        return OSSStorage(
            endpoint=settings.OSS_ENDPOINT,
            access_key=settings.OSS_ACCESS_KEY,
            secret_key=settings.OSS_SECRET_KEY,
            bucket=settings.OSS_BUCKET,
            cdn_domain=settings.OSS_CDN_DOMAIN,
        )

    if backend == "minio":
        from app.core.storage.minio_storage import MinIOStorage
        return MinIOStorage(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            bucket=settings.MINIO_BUCKET,
            secure=settings.MINIO_SECURE,
            cdn_domain=settings.MINIO_CDN_DOMAIN,
        )

    raise ValueError(
        f"未知的存储后端：{backend}。可选值：local / oss / minio"
    )
