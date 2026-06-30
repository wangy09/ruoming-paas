"""
若茗 PaaS - 系统监控 API
包含服务监控（server）和计划任务（task）两个子模块
Author: ruoming
"""
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.response import ok
from app.database import get_db
from app.modules.monitor.server_service import ServerMonitorService
from app.modules.monitor.task_service import TaskService
from app.modules.user.models import SysUser
from app.core.utils.pagination import PageParams

router = APIRouter()

# ══════════════════════════════════════════════════════════════
# 服务监控
# ══════════════════════════════════════════════════════════════

@router.get("/server/info", summary="系统基础信息")
async def server_info(
    current_user: Annotated[SysUser, Depends(get_current_user)],
):
    """获取系统基础信息（OS、主机名、内核版本、运行时长等），一次性加载"""
    data = ServerMonitorService.get_system_info()
    return ok(data)


@router.get("/server/metrics", summary="实时性能指标")
async def server_metrics(
    current_user: Annotated[SysUser, Depends(get_current_user)],
):
    """获取 CPU / 内存 / Swap / 磁盘使用率，供前端轮询"""
    data = ServerMonitorService.get_metrics()
    return ok(data)


@router.get("/server/network", summary="网络流量统计")
async def server_network(
    current_user: Annotated[SysUser, Depends(get_current_user)],
    iface: str | None = Query(None, description="指定网卡名称，不传则返回第一块非 lo 网卡"),
):
    """获取网卡列表及各网卡收发流量统计"""
    data = ServerMonitorService.get_network(iface=iface)
    return ok(data)


# ══════════════════════════════════════════════════════════════
# 计划任务
# ══════════════════════════════════════════════════════════════

@router.get("/tasks/functions", summary="获取可用 Celery Task 列表")
async def list_functions(
    current_user: Annotated[SysUser, Depends(get_current_user)],
):
    """自动扫描 Celery 已注册任务，返回下拉框数据"""
    data = TaskService.get_available_functions()
    return ok(data)


@router.get("/tasks", summary="计划任务列表")
async def list_tasks(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(get_current_user)],
    page_params: Annotated[PageParams, Depends()],
    name: str | None = Query(None, description="任务名称模糊搜索"),
    status: int | None = Query(None, description="状态：1=启用 0=停用"),
):
    svc = TaskService(db)
    data = await svc.list_tasks(page_params, name=name, status=status)
    return ok(data)


@router.post("/tasks", summary="创建计划任务")
async def create_task(
    body: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(get_current_user)],
):
    svc = TaskService(db)
    task = await svc.create_task(body)
    await db.commit()
    return ok({"id": task.id, "name": task.name})


@router.put("/tasks/{task_id}", summary="编辑计划任务")
async def update_task(
    task_id: int,
    body: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(get_current_user)],
):
    svc = TaskService(db)
    task = await svc.update_task(task_id, body)
    await db.commit()
    if not task:
        from app.core.exceptions import AppException
        from app.core.error_codes import SysErrCode
        raise AppException(SysErrCode.NOT_FOUND, "任务不存在")
    return ok({"id": task.id})


@router.delete("/tasks/{task_id}", summary="删除计划任务")
async def delete_task(
    task_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(get_current_user)],
):
    svc = TaskService(db)
    ok_flag = await svc.delete_task(task_id)
    await db.commit()
    if not ok_flag:
        from app.core.exceptions import AppException
        from app.core.error_codes import SysErrCode
        raise AppException(SysErrCode.NOT_FOUND, "任务不存在")
    return ok()


@router.post("/tasks/{task_id}/enable", summary="启用任务")
async def enable_task(
    task_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(get_current_user)],
):
    svc = TaskService(db)
    await svc.set_status(task_id, 1)
    await db.commit()
    return ok()


@router.post("/tasks/{task_id}/disable", summary="停用任务")
async def disable_task(
    task_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(get_current_user)],
):
    svc = TaskService(db)
    await svc.set_status(task_id, 0)
    await db.commit()
    return ok()


@router.post("/tasks/{task_id}/run", summary="立即执行任务")
async def run_task_now(
    task_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(get_current_user)],
):
    svc = TaskService(db)
    result = await svc.run_now(task_id)
    await db.commit()
    return ok(result)


# ── 执行日志 ──────────────────────────────────────────────────

@router.get("/tasks/{task_id}/logs", summary="某任务执行日志")
async def list_task_logs(
    task_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(get_current_user)],
    page_params: Annotated[PageParams, Depends()],
    status: str | None = Query(None, description="状态过滤：pending/running/success/failed"),
):
    svc = TaskService(db)
    data = await svc.list_logs(task_id=task_id, page_params=page_params, status=status)
    return ok(data)


@router.get("/tasks/logs/all", summary="所有任务执行日志")
async def list_all_logs(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(get_current_user)],
    page_params: Annotated[PageParams, Depends()],
    status: str | None = Query(None),
):
    svc = TaskService(db)
    data = await svc.list_logs(task_id=None, page_params=page_params, status=status)
    return ok(data)


@router.delete("/tasks/logs", summary="清空执行日志")
async def clear_logs(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[SysUser, Depends(get_current_user)],
    task_id: int | None = Query(None, description="不传则清空所有"),
    before_date: str | None = Query(None, description="清空此日期之前的日志，格式 YYYY-MM-DD"),
):
    svc = TaskService(db)
    count = await svc.clear_logs(task_id=task_id, before_date=before_date)
    await db.commit()
    return ok({"deleted": count})
