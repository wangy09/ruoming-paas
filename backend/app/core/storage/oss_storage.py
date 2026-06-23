"""阿里云 OSS 存储实现（可选依赖 oss2）"""
from __future__ import annotations

import logging

from app.core.storage.base import FileStorage, StoredObject

logger = logging.getLogger(__name__)


class OSSStorage(FileStorage):
    """阿里云 OSS 存储"""

    backend_name = "oss"

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        cdn_domain: str = "",
    ):
        if not endpoint or not access_key or not secret_key or not bucket:
            raise ValueError("OSS 配置不完整（endpoint/access_key/secret_key/bucket 必填）")
        try:
            import oss2  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "使用 OSS 存储需要安装 oss2：pip install oss2"
            ) from e

        auth = oss2.Auth(access_key, secret_key)
        self.bucket = oss2.Bucket(auth, endpoint, bucket)
        self.endpoint = endpoint.rstrip("/")
        self.cdn_domain = cdn_domain.rstrip("/")
        logger.info(f"OSS storage initialized: bucket={bucket}, endpoint={endpoint}")

    def _public_url(self, key: str) -> str:
        if self.cdn_domain:
            return f"{self.cdn_domain}/{key}"
        return f"https://{self.bucket.bucket_name}.{self.endpoint.split('//', 1)[-1]}/{key}"

    async def put(
        self,
        key: str,
        data: bytes,
        content_type: str | None = None,
    ) -> StoredObject:
        headers = {}
        if content_type:
            headers["Content-Type"] = content_type
        # oss2 本身是同步的，put_object 比较快，这里用 run_in_exholder
        import asyncio
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None, lambda: self.bucket.put_object(key, data, headers=headers)
        )
        return StoredObject(
            key=key,
            url=self._public_url(key),
            backend=self.backend_name,
            size=len(data),
        )

    async def get(self, key: str) -> bytes:
        import asyncio
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self.bucket.get_object, key)
        return result.read()

    async def delete(self, key: str) -> bool:
        import asyncio
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.bucket.delete_object, key)
        return True

    def get_url(self, key: str, expires: int = 3600) -> str:
        """生成带签名的临时访问 URL"""
        import oss2  # type: ignore
        return self.bucket.sign_url("GET", key, expires)
