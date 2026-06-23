"""本地磁盘存储实现"""
from __future__ import annotations

import os
from pathlib import Path

import aiofiles
import aiofiles.os

from app.core.storage.base import FileStorage, StoredObject


class LocalStorage(FileStorage):
    """本地文件系统存储"""

    backend_name = "local"

    def __init__(self, base_dir: str, url_prefix: str = "/static/uploads"):
        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.url_prefix = url_prefix.rstrip("/")

    def _abspath(self, key: str) -> Path:
        # 防止 key 越权访问
        safe_key = key.lstrip("/").replace("..", "")
        path = (self.base_dir / safe_key).resolve()
        if not str(path).startswith(str(self.base_dir)):
            raise ValueError(f"非法的 key：{key}")
        return path

    async def put(
        self,
        key: str,
        data: bytes,
        content_type: str | None = None,
    ) -> StoredObject:
        path = self._abspath(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(path, "wb") as f:
            await f.write(data)
        return StoredObject(
            key=key,
            url=f"{self.url_prefix}/{key}",
            backend=self.backend_name,
            size=len(data),
        )

    async def get(self, key: str) -> bytes:
        path = self._abspath(key)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在：{key}")
        async with aiofiles.open(path, "rb") as f:
            return await f.read()

    async def delete(self, key: str) -> bool:
        path = self._abspath(key)
        if path.exists():
            await aiofiles.os.remove(path)
            return True
        return False

    def get_url(self, key: str, expires: int = 3600) -> str:
        return f"{self.url_prefix}/{key}"
