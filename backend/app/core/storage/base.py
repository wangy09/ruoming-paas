"""
文件存储抽象层

提供统一的文件存储接口，支持 local / oss / minio 等后端。
通过 STORAGE_BACKEND 配置项选择具体实现。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class StoredObject:
    """存储对象信息"""
    key: str                # 对象在存储中的唯一 key（不含后端）
    url: str                # 可访问的 URL（本地为相对路径，OSS 为公网 URL）
    backend: str            # 存储后端类型
    size: int               # 文件大小（字节）


class FileStorage(ABC):
    """文件存储抽象接口"""

    backend_name: str = "abstract"

    @abstractmethod
    async def put(
        self,
        key: str,
        data: bytes,
        content_type: str | None = None,
    ) -> StoredObject:
        """
        上传文件到存储后端
        :param key: 对象 key，相对路径（如 knowledge/2026/06/abc.pdf）
        :param data: 文件二进制内容
        :param content_type: MIME 类型
        :return: StoredObject
        """

    @abstractmethod
    async def get(self, key: str) -> bytes:
        """
        读取文件内容
        :param key: 对象 key
        :return: 文件二进制
        """

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """
        删除文件
        :param key: 对象 key
        :return: 是否成功
        """

    @abstractmethod
    def get_url(self, key: str, expires: int = 3600) -> str:
        """
        获取对象的可访问 URL
        :param key: 对象 key
        :param expires: 签名 URL 过期时间（秒），仅 OSS/MinIO 有效
        """
