"""
若茗 PaaS - 代码生成器路由
"""
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_permissions
from app.core.response import ApiResponse, ok
from app.database import get_db
from app.modules.codegen.schemas import (
    ColumnInfo,
    GeneratePreviewRequest,
    GeneratePreviewResponse,
    GenerateWriteRequest,
    GenerateWriteResponse,
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
    svc = CodegenService(db)
    return ok(await svc.list_tables(keyword))


@router.get("/tables/{table_name}/columns", response_model=ApiResponse[list[ColumnInfo]], summary="表字段列表")
async def list_columns(
    table_name: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("dev:codegen:view"))],
) -> ApiResponse[list[ColumnInfo]]:
    svc = CodegenService(db)
    return ok(await svc.list_columns(table_name))


@router.post("/preview", response_model=ApiResponse[GeneratePreviewResponse], summary="生成代码预览")
async def preview_code(
    body: GeneratePreviewRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("dev:codegen:preview"))],
) -> ApiResponse[GeneratePreviewResponse]:
    svc = CodegenService(db)
    return ok(await svc.preview(body))


@router.post("/write", response_model=ApiResponse[GenerateWriteResponse], summary="写入生成代码")
async def write_code(
    body: GenerateWriteRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("dev:codegen:write"))],
) -> ApiResponse[GenerateWriteResponse]:
    svc = CodegenService(db)
    return ok(await svc.write(body), message="生成完成")
