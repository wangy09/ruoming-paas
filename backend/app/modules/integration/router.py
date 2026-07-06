"""
若茗 PaaS - 第三方协作平台集成 API
"""
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_permissions
from app.core.response import ApiResponse, ok
from app.database import get_db
from app.modules.integration.registry import integration_registry
from app.modules.integration.schemas import (
    ContactSyncStrategy,
    IntegrationConnectionCreate,
    IntegrationConnectionOut,
    IntegrationConnectionUpdate,
    IntegrationSendMessageRequest,
    IntegrationSendMessageResult,
    IntegrationTestResult,
    ProviderInfo,
)
from app.modules.integration.service import IntegrationService
from app.modules.user.models import SysUser

router = APIRouter()


@router.get("/providers", response_model=ApiResponse[list[ProviderInfo]], summary="支持的平台列表")
async def list_providers(
    current_user: Annotated[SysUser, Depends(require_permissions("integration:view"))],
) -> ApiResponse[list[ProviderInfo]]:
    _ = current_user
    return ok(integration_registry.list_providers())


@router.get("/connections", response_model=ApiResponse[list[IntegrationConnectionOut]], summary="集成连接列表")
async def list_connections(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("integration:view"))],
    provider: str | None = Query(None, description="平台：feishu/dingtalk/wecom"),
    enabled: bool | None = Query(None, description="是否启用"),
) -> ApiResponse[list[IntegrationConnectionOut]]:
    svc = IntegrationService(db, current_user)
    return ok(await svc.list_connections(provider=provider, enabled=enabled))


@router.post("/connections", response_model=ApiResponse[IntegrationConnectionOut], summary="创建集成连接")
async def create_connection(
    body: IntegrationConnectionCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("integration:manage"))],
) -> ApiResponse[IntegrationConnectionOut]:
    svc = IntegrationService(db, current_user)
    conn = await svc.create_connection(body)
    await db.commit()
    await db.refresh(conn)
    return ok(svc.to_output(conn), message="创建成功")


@router.put("/connections/{connection_id}", response_model=ApiResponse[IntegrationConnectionOut], summary="更新集成连接")
async def update_connection(
    connection_id: int,
    body: IntegrationConnectionUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("integration:manage"))],
) -> ApiResponse[IntegrationConnectionOut]:
    svc = IntegrationService(db, current_user)
    conn = await svc.update_connection(connection_id, body)
    await db.commit()
    await db.refresh(conn)
    return ok(svc.to_output(conn), message="保存成功")


@router.delete("/connections/{connection_id}", response_model=ApiResponse, summary="删除集成连接")
async def delete_connection(
    connection_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("integration:manage"))],
) -> ApiResponse:
    svc = IntegrationService(db, current_user)
    await svc.delete_connection(connection_id)
    await db.commit()
    return ok(message="删除成功")


@router.post(
    "/connections/{connection_id}/test",
    response_model=ApiResponse[IntegrationTestResult],
    summary="测试集成连接",
)
async def test_connection(
    connection_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("integration:manage"))],
) -> ApiResponse[IntegrationTestResult]:
    svc = IntegrationService(db, current_user)
    result = await svc.test_connection(connection_id)
    await db.commit()
    return ok(result)


@router.get(
    "/connections/{connection_id}/contact-sync-strategy",
    response_model=ApiResponse[ContactSyncStrategy],
    summary="获取通讯录同步默认策略",
)
async def get_contact_sync_strategy(
    connection_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("system:user:sync"))],
) -> ApiResponse[ContactSyncStrategy]:
    svc = IntegrationService(db, current_user)
    return ok(await svc.get_contact_sync_strategy(connection_id))


@router.put(
    "/connections/{connection_id}/contact-sync-strategy",
    response_model=ApiResponse[ContactSyncStrategy],
    summary="保存通讯录同步默认策略",
)
async def save_contact_sync_strategy(
    connection_id: int,
    body: ContactSyncStrategy,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(require_permissions("system:user:sync"))],
) -> ApiResponse[ContactSyncStrategy]:
    svc = IntegrationService(db, current_user)
    strategy = await svc.save_contact_sync_strategy(connection_id, body)
    await db.commit()
    return ok(strategy, message="保存成功")


@router.post("/messages/send", response_model=ApiResponse[IntegrationSendMessageResult], summary="统一发送协作平台消息")
async def send_message(
    body: IntegrationSendMessageRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(get_current_user)],
) -> ApiResponse[IntegrationSendMessageResult]:
    svc = IntegrationService(db, current_user)
    return ok(await svc.send_message(body))
