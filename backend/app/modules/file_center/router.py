"""
若茗 PaaS - 文件中心 API
"""
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.deps import get_current_user, require_permissions
from app.core.exceptions import ValidationException
from app.core.response import ApiResponse, ok
from app.core.utils.pagination import PageParams
from app.database import get_db
from app.modules.file_center.schemas import (
    FileArchiveRequest,
    FileInfo,
    FileUpdateRequest,
    StorageConfigInfo,
)
from app.modules.file_center.service import FileCenterService
from app.modules.user.models import SysUser

router = APIRouter()


@router.get("/storage/config", response_model=ApiResponse[StorageConfigInfo], summary="存储配置摘要")
async def storage_config(
    current_user: Annotated[SysUser, Depends(require_permissions("system:file:view"))],
) -> ApiResponse[StorageConfigInfo]:
    return ok(StorageConfigInfo(
        backend=settings.STORAGE_BACKEND,
        upload_dir=settings.UPLOAD_DIR if settings.STORAGE_BACKEND == "local" else None,
        max_upload_size_mb=settings.MAX_UPLOAD_SIZE_MB,
        allowed_extensions=settings.ALLOWED_UPLOAD_EXTENSIONS,
        supports=["local", "minio", "oss"],
    ))


@router.get("", response_model=ApiResponse, summary="文件列表")
async def list_files(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("system:file:view"))],
    page_params: Annotated[PageParams, Depends()],
    keyword: str | None = Query(None, description="文件名/备注关键字"),
    status: int | None = Query(None, description="状态：1正常 2已归档"),
    biz_type: str | None = Query(None, description="业务类型"),
    category: str | None = Query(None, description="文件分类"),
    file_ext: str | None = Query(None, description="扩展名"),
) -> ApiResponse:
    tenant_id = None if current_user.is_superplatform else current_user.tenant_id
    svc = FileCenterService(db, tenant_id)
    data = await svc.list_files(
        page_params,
        keyword=keyword,
        status=status,
        biz_type=biz_type,
        category=category,
        file_ext=file_ext,
    )
    data["items"] = [FileInfo.model_validate(item) for item in data["items"]]
    return ok(data)


@router.post("/upload", response_model=ApiResponse[FileInfo], summary="上传文件")
async def upload_file(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("system:file:upload"))],
    file: UploadFile = File(..., description="上传文件"),
    biz_type: str | None = Form(None),
    biz_id: str | None = Form(None),
    category: str | None = Form(None),
    remark: str | None = Form(None),
    is_public: bool = Form(False),
) -> ApiResponse[FileInfo]:
    tenant_id = None if current_user.is_superplatform else current_user.tenant_id
    svc = FileCenterService(db, tenant_id)
    record = await svc.upload_file(
        file,
        current_user=current_user,
        biz_type=biz_type,
        biz_id=biz_id,
        category=category,
        remark=remark,
        is_public=is_public,
    )
    await db.commit()
    await db.refresh(record)
    return ok(FileInfo.model_validate(record), message="上传成功")


@router.get("/{file_id}", response_model=ApiResponse[FileInfo], summary="文件详情")
async def get_file(
    file_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("system:file:view"))],
) -> ApiResponse[FileInfo]:
    tenant_id = None if current_user.is_superplatform else current_user.tenant_id
    svc = FileCenterService(db, tenant_id)
    record = await svc.get_file(file_id)
    return ok(FileInfo.model_validate(record))


@router.put("/{file_id}", response_model=ApiResponse[FileInfo], summary="更新文件元信息")
async def update_file(
    file_id: int,
    body: FileUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("system:file:update"))],
) -> ApiResponse[FileInfo]:
    tenant_id = None if current_user.is_superplatform else current_user.tenant_id
    svc = FileCenterService(db, tenant_id)
    record = await svc.update_file(file_id, body)
    await db.commit()
    await db.refresh(record)
    return ok(FileInfo.model_validate(record), message="保存成功")


@router.get("/{file_id}/preview", summary="预览文件")
async def preview_file(
    file_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("system:file:preview"))],
) -> Response:
    tenant_id = None if current_user.is_superplatform else current_user.tenant_id
    svc = FileCenterService(db, tenant_id)
    record = await svc.get_file(file_id)
    if not svc.can_preview(record):
        raise ValidationException("该文件类型暂不支持在线预览，请下载后查看")

    content = await svc.get_content(record)
    filename = quote(record.original_name)
    return Response(
        content,
        media_type=record.mime_type or "application/octet-stream",
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{filename}"},
    )


@router.get("/{file_id}/download", summary="下载文件")
async def download_file(
    file_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("system:file:download"))],
) -> Response:
    tenant_id = None if current_user.is_superplatform else current_user.tenant_id
    svc = FileCenterService(db, tenant_id)
    record = await svc.get_file(file_id)
    content = await svc.get_content(record)
    await svc.increase_download_count(record)
    await db.commit()

    filename = quote(record.original_name)
    return Response(
        content,
        media_type=record.mime_type or "application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


@router.post("/{file_id}/archive", response_model=ApiResponse[FileInfo], summary="归档文件")
async def archive_file(
    file_id: int,
    body: FileArchiveRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("system:file:archive"))],
) -> ApiResponse[FileInfo]:
    tenant_id = None if current_user.is_superplatform else current_user.tenant_id
    svc = FileCenterService(db, tenant_id)
    record = await svc.archive_file(file_id, current_user, body.reason)
    await db.commit()
    await db.refresh(record)
    return ok(FileInfo.model_validate(record), message="归档成功")


@router.post("/{file_id}/restore", response_model=ApiResponse[FileInfo], summary="恢复归档文件")
async def restore_file(
    file_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("system:file:archive"))],
) -> ApiResponse[FileInfo]:
    tenant_id = None if current_user.is_superplatform else current_user.tenant_id
    svc = FileCenterService(db, tenant_id)
    record = await svc.restore_file(file_id)
    await db.commit()
    await db.refresh(record)
    return ok(FileInfo.model_validate(record), message="恢复成功")


@router.delete("/{file_id}", response_model=ApiResponse, summary="删除文件记录")
async def delete_file(
    file_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("system:file:delete"))],
) -> ApiResponse:
    tenant_id = None if current_user.is_superplatform else current_user.tenant_id
    svc = FileCenterService(db, tenant_id)
    await svc.delete_file(file_id)
    await db.commit()
    return ok(message="删除成功")
