from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_permissions
from app.core.response import ApiResponse, ok
from app.core.utils.pagination import PageParams
from app.database import get_db
from app.modules.{{ module_name }}.schemas import {{ entity_name }}Create, {{ entity_name }}Info, {{ entity_name }}Update
from app.modules.{{ module_name }}.service import {{ entity_name }}Service
from app.modules.user.models import SysUser

router = APIRouter()


@router.get("", response_model=ApiResponse, summary="{{ page_title }}列表")
async def list_items(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("{{ module_name }}:view"))],
    page_params: Annotated[PageParams, Depends()],
    keyword: str | None = None,
) -> ApiResponse:
    svc = {{ entity_name }}Service(db, current_user.tenant_id)
    data = await svc.list(page_params, keyword)
    data["items"] = [{{ entity_name }}Info.model_validate(item) for item in data["items"]]
    return ok(data)


@router.post("", response_model=ApiResponse[{{ entity_name }}Info], summary="创建{{ page_title }}")
async def create_item(
    body: {{ entity_name }}Create,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("{{ module_name }}:create"))],
) -> ApiResponse[{{ entity_name }}Info]:
    svc = {{ entity_name }}Service(db, current_user.tenant_id)
    obj = await svc.create(body)
    await db.commit()
    await db.refresh(obj)
    return ok({{ entity_name }}Info.model_validate(obj), message="创建成功")


@router.get("/{obj_id}", response_model=ApiResponse[{{ entity_name }}Info], summary="{{ page_title }}详情")
async def get_item(
    obj_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("{{ module_name }}:view"))],
) -> ApiResponse[{{ entity_name }}Info]:
    svc = {{ entity_name }}Service(db, current_user.tenant_id)
    obj = await svc.get(obj_id)
    return ok({{ entity_name }}Info.model_validate(obj))


@router.put("/{obj_id}", response_model=ApiResponse[{{ entity_name }}Info], summary="编辑{{ page_title }}")
async def update_item(
    obj_id: int,
    body: {{ entity_name }}Update,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("{{ module_name }}:update"))],
) -> ApiResponse[{{ entity_name }}Info]:
    svc = {{ entity_name }}Service(db, current_user.tenant_id)
    obj = await svc.update(obj_id, body)
    await db.commit()
    await db.refresh(obj)
    return ok({{ entity_name }}Info.model_validate(obj), message="保存成功")


@router.delete("/{obj_id}", response_model=ApiResponse, summary="删除{{ page_title }}")
async def delete_item(
    obj_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("{{ module_name }}:delete"))],
) -> ApiResponse:
    svc = {{ entity_name }}Service(db, current_user.tenant_id)
    await svc.delete(obj_id)
    await db.commit()
    return ok(message="删除成功")