"""
若茗 PaaS - 工具管理路由
/api/v1/ai/tools
Author: ruoming
"""
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.tool.registry import ToolRegistry
from app.core.deps import get_current_user, require_permissions
from app.core.response import ApiResponse, ok
from app.database import get_db
from app.modules.user.models import SysUser

router = APIRouter(prefix="/ai/tools", tags=["AI-工具管理"])


class ToolInfo(BaseModel):
    tool_id: str
    name: str
    description: str


@router.get("", response_model=ApiResponse[list[ToolInfo]], summary="工具列表（含内置+自定义）")
async def list_tools(
    _: SysUser = Depends(get_current_user),
):
    registry = ToolRegistry()
    tools = registry.list_all()
    return ok([ToolInfo(**t) for t in tools])
