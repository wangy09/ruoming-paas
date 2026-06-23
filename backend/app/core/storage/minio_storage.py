"""MinIO / S3 兼容存储实现（可选依赖 minio）"""
from __future__ import annotations

import logging

from app.core.storage.base import FileStorage, StoredObject

logger = logging.getLogger(__name__)


class MinIOStorage(FileStorage):
    """MinIO / S3 兼容存储"""

    backend_name = "minio"

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool = False,
        cdn_domain: str = "",
    ):
        if not endpoint or not access_key or not secret_key or not bucket:
            raise ValueError("MinIO 配置不完整（endpoint/access_key/secret_key/bucket 必填）")
        try:
            from minio import Minio  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "使用 MinIO 存储需要安装 minio：pip install minio"
            ) from e

        self.client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
        )
        self.bucket = bucket
        self.cdn_domain = cdn_domain.rstrip("/")
        # 自动创建 bucket
        try:
            if not self.client.bucket_exists(bucket):
                self.client.make_bucket(bucket)
                logger.info(f"MinIO bucket created: {bucket}")
        except Exception as e:
            logger.warning(f"MinIO bucket 检查/创建失败：{e}")

    def _public_url(self, key: str) -> str:
        if self.cdn_domain:
            return f"{self.cdn_domain}/{key}"
        scheme = "https" if self.client._http.url.scheme == "https" else "http"  # noqa
        return f"{scheme}://{self.client._http.url.netloc}/{self.bucket}/{key}"  # noqa

    async def put(
        self,
        key: str,
        data: bytes,
        content_type: str | None = None,
    ) -> StoredObject:
        import io
        import asyncio
        loop = asyncio.get_event_loop()
        from minio import PutObject  # type: ignore
        data_stream = io.BytesIO(data)
        length = len(data)
        await loop.run_in_executor(
            None,
            lambda: self.client.put_object(
                self.bucket, key, data_stream, length, content_type=content_type
            ),
        )
        return StoredObject(
            key=key,
            url=self._public_url(key),
            backend=self.backend_name,
            size=length,
        )

    async def get(self, key: str) -> bytes:
        import asyncio
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, self.client.get_object, self.bucket, key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    async def delete(self, key: str) -> bool:
        import asyncio
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.client.remove_object, self.bucket, key)
        return True

    def get_url(self, key: str, expires: int = 3600) -> str:
        """生成预签名 URL"""
        from datetime import timedelta
        return self.client.presigned_get_object(
            self.bucket, key, expires=timedelta(seconds=expires)
        )
