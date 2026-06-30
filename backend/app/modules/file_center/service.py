"""
若茗 PaaS - 文件中心服务
"""
from __future__ import annotations

import hashlib
import mimetypes
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import NotFoundException, ValidationException
from app.core.storage.factory import get_storage
from app.core.utils.pagination import PageParams
from app.modules.file_center.models import SysFile
from app.modules.file_center.schemas import FileUpdateRequest
from app.modules.user.models import SysUser


PREVIEW_MIME_PREFIXES = ("image/", "text/", "audio/", "video/")
PREVIEW_MIME_TYPES = {
    "application/pdf",
    "application/json",
    "application/xml",
}


class FileCenterService:
    """文件中心服务"""

    def __init__(self, db: AsyncSession, tenant_id: int | None = None):
        self.db = db
        self.tenant_id = tenant_id

    async def list_files(
        self,
        page_params: PageParams,
        *,
        keyword: str | None = None,
        status: int | None = None,
        biz_type: str | None = None,
        category: str | None = None,
        file_ext: str | None = None,
    ) -> dict:
        stmt = select(SysFile).where(SysFile.is_deleted == False)  # noqa: E712
        stmt = self._scope(stmt)

        if keyword:
            like = f"%{keyword}%"
            stmt = stmt.where(or_(SysFile.original_name.ilike(like), SysFile.remark.ilike(like)))
        if status:
            stmt = stmt.where(SysFile.status == status)
        if biz_type:
            stmt = stmt.where(SysFile.biz_type == biz_type)
        if category:
            stmt = stmt.where(SysFile.category == category)
        if file_ext:
            stmt = stmt.where(SysFile.file_ext == file_ext.lower().lstrip("."))

        total = await self.db.scalar(select(func.count()).select_from(stmt.subquery()))
        result = await self.db.execute(
            stmt.order_by(SysFile.created_at.desc())
            .offset((page_params.page - 1) * page_params.page_size)
            .limit(page_params.page_size)
        )
        return {
            "items": list(result.scalars().all()),
            "total": total or 0,
            "page": page_params.page,
            "page_size": page_params.page_size,
        }

    async def upload_file(
        self,
        file: UploadFile,
        *,
        current_user: SysUser,
        biz_type: str | None = None,
        biz_id: str | None = None,
        category: str | None = None,
        remark: str | None = None,
        is_public: bool = False,
    ) -> SysFile:
        content = await file.read()
        self._validate_file(file.filename or "", content)

        original_name = Path(file.filename or "unnamed").name
        ext = self._file_ext(original_name)
        file_hash = hashlib.sha256(content).hexdigest()
        object_name = f"{uuid.uuid4().hex}{'.' + ext if ext else ''}"
        date_part = datetime.now(tz=timezone.utc).strftime("%Y/%m/%d")
        storage_key = f"file-center/{date_part}/{object_name}"
        content_type = file.content_type or mimetypes.guess_type(original_name)[0]

        storage = get_storage()
        stored = await storage.put(storage_key, content, content_type=content_type)

        record = SysFile(
            original_name=original_name,
            file_name=object_name,
            file_ext=ext,
            mime_type=content_type,
            file_size=stored.size,
            file_hash=file_hash,
            storage_backend=stored.backend,
            storage_key=stored.key,
            storage_url=stored.url,
            biz_type=biz_type,
            biz_id=biz_id,
            category=category,
            remark=remark,
            is_public=is_public,
            uploader_id=current_user.id,
            tenant_id=None if current_user.is_superplatform else current_user.tenant_id,
        )
        self.db.add(record)
        await self.db.flush()
        return record

    async def get_file(self, file_id: int) -> SysFile:
        stmt = select(SysFile).where(SysFile.id == file_id, SysFile.is_deleted == False)  # noqa: E712
        stmt = self._scope(stmt)
        record = (await self.db.execute(stmt)).scalar_one_or_none()
        if not record:
            raise NotFoundException("文件")
        return record

    async def get_content(self, record: SysFile) -> bytes:
        storage = get_storage()
        return await storage.get(record.storage_key)

    async def increase_download_count(self, record: SysFile) -> None:
        record.download_count += 1
        await self.db.flush()

    async def update_file(self, file_id: int, data: FileUpdateRequest) -> SysFile:
        record = await self.get_file(file_id)
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(record, key, value)
        await self.db.flush()
        return record

    async def archive_file(self, file_id: int, current_user: SysUser, reason: str | None = None) -> SysFile:
        record = await self.get_file(file_id)
        if record.status == 2:
            return record
        record.status = 2
        record.archived_at = datetime.now(tz=timezone.utc)
        record.archived_by = current_user.id
        record.archive_reason = reason
        await self.db.flush()
        return record

    async def restore_file(self, file_id: int) -> SysFile:
        record = await self.get_file(file_id)
        record.status = 1
        record.archived_at = None
        record.archived_by = None
        record.archive_reason = None
        await self.db.flush()
        return record

    async def delete_file(self, file_id: int) -> None:
        record = await self.get_file(file_id)
        record.is_deleted = True
        await self.db.flush()

    @staticmethod
    def can_preview(record: SysFile) -> bool:
        mime_type = record.mime_type or mimetypes.guess_type(record.original_name)[0] or ""
        return mime_type in PREVIEW_MIME_TYPES or mime_type.startswith(PREVIEW_MIME_PREFIXES)

    def _scope(self, stmt: Select) -> Select:
        if self.tenant_id is None:
            return stmt
        return stmt.where(SysFile.tenant_id == self.tenant_id)

    @staticmethod
    def _file_ext(filename: str) -> str:
        return Path(filename).suffix.lower().lstrip(".")

    def _validate_file(self, filename: str, content: bytes) -> None:
        if not content:
            raise ValidationException("不能上传空文件")

        max_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if len(content) > max_size:
            raise ValidationException(f"文件大小不能超过 {settings.MAX_UPLOAD_SIZE_MB}MB")

        ext = self._file_ext(filename)
        allowed = {item.lower().lstrip(".") for item in settings.ALLOWED_UPLOAD_EXTENSIONS}
        if allowed and ext not in allowed:
            allowed_text = "、".join(sorted(allowed))
            raise ValidationException(f"不支持的文件类型：{ext or '无扩展名'}，允许的类型：{allowed_text}")
