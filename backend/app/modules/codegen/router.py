"""
若茗 PaaS - 代码生成器路由
"""
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_permissions
from app.core.response import ApiResponse, ok
from app.database import get_db
from sqlalchemy import select

from app.modules.codegen.models import GenTable
from app.modules.codegen.schemas import (
    BatchGenerateRequest,
    ColumnInfo,
    CreateTableRequest,
    GeneratePreviewRequest,
    GeneratePreviewResponse,
    GenerateWriteRequest,
    GenerateWriteResponse,
    GenTableResponse,
    ListConfigResponse,
    SaveConfigRequest,
    TableInfo,
)
from app.modules.codegen.service import CodegenService
from app.modules.user.models import SysUser

router = APIRouter()


@router.get("/tables", response_model=ApiResponse[list[TableInfo]], summary="数据库表列表")
async def list_tables(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("dev:codegen:view"))],
    keyword: str | None = Query(None, description="表名或注释关键词"),
) -> ApiResponse[list[TableInfo]]:
    tenant_id = None if current_user.is_superplatform else current_user.tenant_id
    svc = CodegenService(db, tenant_id=tenant_id)
    return ok(await svc.list_tables(keyword))


@router.get("/tables/{table_name}/columns", response_model=ApiResponse[list[ColumnInfo]], summary="表字段列表")
async def list_columns(
    table_name: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("dev:codegen:view"))],
) -> ApiResponse[list[ColumnInfo]]:
    tenant_id = None if current_user.is_superplatform else current_user.tenant_id
    svc = CodegenService(db, tenant_id=tenant_id)
    return ok(await svc.list_columns(table_name))


@router.post("/preview", response_model=ApiResponse[GeneratePreviewResponse], summary="生成代码预览")
async def preview_code(
    body: GeneratePreviewRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("dev:codegen:preview"))],
) -> ApiResponse[GeneratePreviewResponse]:
    tenant_id = None if current_user.is_superplatform else current_user.tenant_id
    svc = CodegenService(db, tenant_id=tenant_id)
    return ok(await svc.preview(body))


@router.post("/write", response_model=ApiResponse[GenerateWriteResponse], summary="写入生成代码")
async def write_code(
    body: GenerateWriteRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("dev:codegen:write"))],
) -> ApiResponse[GenerateWriteResponse]:
    tenant_id = None if current_user.is_superplatform else current_user.tenant_id
    svc = CodegenService(db, tenant_id=tenant_id)
    return ok(await svc.write(body), message="生成完成")


@router.get("/configs", response_model=ApiResponse[ListConfigResponse], summary="配置列表")
async def list_configs(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("dev:codegen:view"))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str | None = Query(None),
) -> ApiResponse[ListConfigResponse]:
    tenant_id = None if current_user.is_superplatform else current_user.tenant_id
    svc = CodegenService(db, tenant_id=tenant_id)
    return ok(await svc.list_configs(page, page_size, keyword))


@router.get("/configs/{config_id}", response_model=ApiResponse[GenTableResponse], summary="获取配置")
async def get_config(
    config_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("dev:codegen:view"))],
) -> ApiResponse[GenTableResponse]:
    tenant_id = None if current_user.is_superplatform else current_user.tenant_id
    svc = CodegenService(db, tenant_id=tenant_id)
    return ok(await svc.get_config(config_id))


@router.post("/configs", response_model=ApiResponse[GenTableResponse], summary="保存配置")
async def save_config(
    body: SaveConfigRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("dev:codegen:write"))],
) -> ApiResponse[GenTableResponse]:
    tenant_id = None if current_user.is_superplatform else current_user.tenant_id
    svc = CodegenService(db, tenant_id=tenant_id)
    await svc.save_config(body, current_user.id if hasattr(current_user, 'id') else None)
    query = select(GenTable).where(
        GenTable.table_name == body.table_name,
        GenTable.is_deleted == False
    )
    if tenant_id is not None:
        query = query.where(GenTable.tenant_id == tenant_id)
    config_id = (await db.execute(query)).scalar_one().id
    config = await svc.get_config(config_id)
    return ok(config, message="配置保存成功")


@router.delete("/configs/{config_id}", response_model=ApiResponse[None], summary="删除配置")
async def delete_config(
    config_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("dev:codegen:delete"))],
) -> ApiResponse[None]:
    tenant_id = None if current_user.is_superplatform else current_user.tenant_id
    svc = CodegenService(db, tenant_id=tenant_id)
    await svc.delete_config(config_id)
    return ok(None, message="配置已删除")


@router.post("/configs/{config_id}/generate", response_model=ApiResponse[GenerateWriteResponse], summary="从配置生成代码")
async def generate_from_config(
    config_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("dev:codegen:write"))],
    overwrite: bool = False,
) -> ApiResponse[GenerateWriteResponse]:
    tenant_id = None if current_user.is_superplatform else current_user.tenant_id
    svc = CodegenService(db, tenant_id=tenant_id)
    return ok(await svc.generate_from_config(config_id, overwrite), message="生成完成")


@router.post("/configs/batch-generate", response_model=ApiResponse[list], summary="批量生成代码")
async def batch_generate(
    body: BatchGenerateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("dev:codegen:write"))],
) -> ApiResponse[list]:
    tenant_id = None if current_user.is_superplatform else current_user.tenant_id
    svc = CodegenService(db, tenant_id=tenant_id)
    return ok(await svc.batch_generate(body), message="批量生成完成")


@router.get("/configs/{config_id}/download", summary="下载生成代码 ZIP")
async def download_code(
    config_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("dev:codegen:write"))],
) -> StreamingResponse:
    tenant_id = None if current_user.is_superplatform else current_user.tenant_id
    svc = CodegenService(db, tenant_id=tenant_id)
    config = await svc.get_config(config_id)
    zip_content = await svc.generate_zip(config_id)
    return StreamingResponse(
        iter([zip_content]),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={config['module_name']}_codegen.zip"},
    )


@router.get("/field-types", response_model=ApiResponse, summary="获取支持的字段类型")
async def get_field_types() -> ApiResponse:
    return ok(CodegenService._get_supported_field_types())


@router.post("/create-table", summary="前端建表（创建数据库表并保存配置）")
async def create_table(
    request: CreateTableRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("dev:codegen:write"))],
) -> dict:
    tenant_id = None if current_user.is_superplatform else current_user.tenant_id
    svc = CodegenService(db, tenant_id=tenant_id)
    result = await svc.create_table_from_config(request, current_user.id)
    return result
