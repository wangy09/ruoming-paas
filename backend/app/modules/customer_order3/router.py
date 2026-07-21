from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_permissions
from app.core.response import ApiResponse, ok
from app.core.utils.pagination import PageParams
from app.database import get_db
from app.modules.customer_order3.schemas import CustomerOrder3Create, CustomerOrder3Info, CustomerOrder3Update
from app.modules.customer_order3.service import CustomerOrder3Service
from app.modules.user.models import SysUser

router = APIRouter()


@router.get("", response_model=ApiResponse, summary="客户订单列表")
async def list_items(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("customer_order3:view"))],
    page_params: Annotated[PageParams, Depends()],
    keyword: str | None = None,
) -> ApiResponse:
    svc = CustomerOrder3Service(db, current_user.tenant_id)
    data = await svc.list(page_params, keyword)
    data["items"] = [CustomerOrder3Info.model_validate(item) for item in data["items"]]
    return ok(data)


@router.post("", response_model=ApiResponse[CustomerOrder3Info], summary="创建客户订单")
async def create_item(
    body: CustomerOrder3Create,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("customer_order3:create"))],
) -> ApiResponse[CustomerOrder3Info]:
    svc = CustomerOrder3Service(db, current_user.tenant_id)
    obj = await svc.create(body)
    await db.commit()
    await db.refresh(obj)
    return ok(CustomerOrder3Info.model_validate(obj), message="创建成功")


@router.get("/{obj_id}", response_model=ApiResponse[CustomerOrder3Info], summary="客户订单详情")
async def get_item(
    obj_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("customer_order3:view"))],
) -> ApiResponse[CustomerOrder3Info]:
    svc = CustomerOrder3Service(db, current_user.tenant_id)
    obj = await svc.get(obj_id)
    return ok(CustomerOrder3Info.model_validate(obj))


@router.put("/{obj_id}", response_model=ApiResponse[CustomerOrder3Info], summary="编辑客户订单")
async def update_item(
    obj_id: int,
    body: CustomerOrder3Update,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("customer_order3:update"))],
) -> ApiResponse[CustomerOrder3Info]:
    svc = CustomerOrder3Service(db, current_user.tenant_id)
    obj = await svc.update(obj_id, body)
    await db.commit()
    await db.refresh(obj)
    return ok(CustomerOrder3Info.model_validate(obj), message="保存成功")


@router.delete("/{obj_id}", response_model=ApiResponse, summary="删除客户订单")
async def delete_item(
    obj_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("customer_order3:delete"))],
) -> ApiResponse:
    svc = CustomerOrder3Service(db, current_user.tenant_id)
    await svc.delete(obj_id)
    await db.commit()
    return ok(message="删除成功")