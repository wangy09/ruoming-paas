"""
若茗 PaaS - 工具管理路由
/api/v1/ai/tools
Author: ruoming
"""
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.tool.models import AiTool
from app.ai.tool.registry import ToolRegistry
from app.core.deps import get_current_user
from app.core.exceptions import NotFoundException
from app.core.response import ApiResponse, ok, created
from app.database import get_db
from app.modules.user.models import SysUser

router = APIRouter(prefix="/ai/tools", tags=["AI-工具管理"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class ToolInfo(BaseModel):
    tool_id: str
    name: str
    description: str
    tool_type: str = "builtin"   # builtin / api
    db_id: int | None = None     # 数据库 ID（自定义工具才有）
    status: int = 1
    url: str | None = None
    method: str | None = None
    headers: dict = Field(default_factory=dict)


class CustomToolCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    description: str = Field("", max_length=500)
    url: str = Field(..., min_length=1, max_length=500)
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH"] = "POST"
    headers: dict = Field(default_factory=dict)


class CustomToolUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=64)
    description: str | None = Field(None, max_length=500)
    url: str | None = Field(None, min_length=1, max_length=500)
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH"] | None = None
    headers: dict | None = None
    status: int | None = None


class CustomToolOut(BaseModel):
    id: int
    name: str
    description: str | None
    tool_type: str
    url: str | None
    method: str | None
    headers: dict
    status: int

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_tool(cls, t: AiTool) -> "CustomToolOut":
        cfg = t.config or {}
        return cls(
            id=t.id,
            name=t.name,
            description=t.description,
            tool_type=t.tool_type,
            url=cfg.get("url"),
            method=cfg.get("method", "POST"),
            headers=cfg.get("headers", {}),
            status=t.status,
        )


# ── 启动时加载自定义工具到注册中心 ─────────────────────────────────────────────

async def load_custom_tools_from_db(db: AsyncSession) -> None:
    """应用启动时调用，将数据库中的自定义工具加载到 ToolRegistry"""
    result = await db.execute(
        select(AiTool).where(
            and_(AiTool.tool_type.in_(["api", "custom"]), AiTool.is_deleted == False, AiTool.status == 1)  # noqa: E712
        )
    )
    tools = result.scalars().all()
    for t in tools:
        cfg = t.config or {}
        ToolRegistry.register_api_tool(
            tool_id=t.code,
            name=t.name,
            description=t.description or "",
            url=cfg.get("url", ""),
            method=cfg.get("method", "POST"),
            headers=cfg.get("headers", {}),
        )


# ── 路由 ───────────────────────────────────────────────────────────────────────

@router.get("", response_model=ApiResponse[list[ToolInfo]], summary="工具列表（含内置+自定义）")
async def list_tools(
    db: AsyncSession = Depends(get_db),
    _: SysUser = Depends(get_current_user),
):
    """获取所有可用工具，内置工具来自注册中心，自定义工具同步数据库状态"""
    # 从注册中心拿内置工具
    registry_tools = {t["tool_id"]: t for t in ToolRegistry.list_all()}

    # 从 DB 拿自定义工具补充详情
    result = await db.execute(
        select(AiTool).where(
            and_(AiTool.tool_type.in_(["api", "custom"]), AiTool.is_deleted == False)  # noqa: E712
        ).order_by(AiTool.id)
    )
    db_tools = result.scalars().all()
    db_codes = {t.code for t in db_tools}

    out: list[ToolInfo] = []

    # 内置工具
    for tid, info in registry_tools.items():
        if tid not in db_codes:  # 非自定义
            out.append(ToolInfo(tool_id=tid, name=info["name"], description=info["description"], tool_type="builtin"))

    # 自定义工具
    for t in db_tools:
        cfg = t.config or {}
        out.append(ToolInfo(
            tool_id=t.code,
            name=t.name,
            description=t.description or "",
            tool_type=t.tool_type,
            db_id=t.id,
            status=t.status,
            url=cfg.get("url"),
            method=cfg.get("method", "POST"),
            headers=cfg.get("headers", {}),
        ))

    return ok(out)


@router.post("", response_model=ApiResponse[CustomToolOut], summary="新建自定义工具（API类型）")
async def create_tool(
    body: CustomToolCreate,
    db: AsyncSession = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    tool = AiTool(
        name=body.name,
        code="custom:placeholder",   # 先占位，flush 后用 id 重写
        description=body.description,
        tool_type="api",
        config={
            "url": body.url,
            "method": body.method,
            "headers": body.headers,
        },
        status=1,
    )
    db.add(tool)
    await db.flush()  # 拿到自增 id

    # 用自增 ID 生成唯一、可读的 code
    code = f"custom:tool_{tool.id}"
    tool.code = code

    # 注册到运行时
    ToolRegistry.register_api_tool(
        tool_id=code,
        name=body.name,
        description=body.description,
        url=body.url,
        method=body.method,
        headers=body.headers,
    )

    await db.commit()
    await db.refresh(tool)
    return created(CustomToolOut.from_orm_tool(tool))


@router.put("/{tool_id}", response_model=ApiResponse[CustomToolOut], summary="更新自定义工具")
async def update_tool(
    tool_id: int,
    body: CustomToolUpdate,
    db: AsyncSession = Depends(get_db),
    _: SysUser = Depends(get_current_user),
):
    result = await db.execute(
        select(AiTool).where(and_(AiTool.id == tool_id, AiTool.is_deleted == False))  # noqa: E712
    )
    tool = result.scalar_one_or_none()
    if not tool:
        raise NotFoundException(f"工具 ID={tool_id} 不存在")
    if tool.tool_type == "builtin":
        from app.core.exceptions import AppException
        from app.core.error_codes import SysErrCode
        raise AppException(code=SysErrCode.FORBIDDEN, message="内置工具不允许修改", http_status=403)

    cfg = dict(tool.config or {})
    if body.name is not None:
        tool.name = body.name
    if body.description is not None:
        tool.description = body.description
    if body.url is not None:
        cfg["url"] = body.url
    if body.method is not None:
        cfg["method"] = body.method
    if body.headers is not None:
        cfg["headers"] = body.headers
    if body.status is not None:
        tool.status = body.status
    tool.config = cfg

    # 重新注册（覆盖）或注销
    if tool.status == 1:
        ToolRegistry.register_api_tool(
            tool_id=tool.code,
            name=tool.name,
            description=tool.description or "",
            url=cfg.get("url", ""),
            method=cfg.get("method", "POST"),
            headers=cfg.get("headers", {}),
        )
    else:
        ToolRegistry.unregister(tool.code)

    await db.commit()
    await db.refresh(tool)
    return ok(CustomToolOut.from_orm_tool(tool))


@router.delete("/{tool_id}", response_model=ApiResponse, summary="删除自定义工具")
async def delete_tool(
    tool_id: int,
    db: AsyncSession = Depends(get_db),
    _: SysUser = Depends(get_current_user),
):
    result = await db.execute(
        select(AiTool).where(and_(AiTool.id == tool_id, AiTool.is_deleted == False))  # noqa: E712
    )
    tool = result.scalar_one_or_none()
    if not tool:
        raise NotFoundException(f"工具 ID={tool_id} 不存在")
    if tool.tool_type == "builtin":
        from app.core.exceptions import AppException
        from app.core.error_codes import SysErrCode
        raise AppException(code=SysErrCode.FORBIDDEN, message="内置工具不允许删除", http_status=403)

    tool.is_deleted = True
    ToolRegistry.unregister(tool.code)
    await db.commit()
    return ok(message="删除成功")
