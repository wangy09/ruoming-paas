"""
若茗 PaaS - 系统监控 API
包含服务监控（server）、计划任务（task）和熔断器监控（circuit）三个子模块
Author: ruoming
"""
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_permissions
from app.core.response import ok
from app.database import get_db
from app.modules.monitor.server_service import ServerMonitorService
from app.modules.monitor.task_service import TaskService
from app.modules.user.models import SysUser
from app.core.utils.pagination import PageParams

router = APIRouter()


# ══════════════════════════════════════════════════════════════
# 熔断器监控
# ══════════════════════════════════════════════════════════════

@router.get("/circuit/breakers", summary="熔断器状态列表")
async def list_circuit_breakers(
    current_user: Annotated[SysUser, Depends(require_permissions("monitor:circuit:view"))],
    db: AsyncSession = Depends(get_db),
):
    """
    获取所有服务的熔断器状态，包括：
    - LLM: AI 模型调用
    - INTEGRATION: 第三方集成（飞书、钉钉、企微）
    - WEBSEARCH: 网页搜索
    - CODEGEN: 代码生成
    
    状态说明：
    - CLOSED: 正常，熔断器关闭
    - OPEN: 熔断中，自动切换到备用模型
    - HALF_OPEN: 半开状态，允许部分请求尝试恢复
    """
    import time
    from app.core.redis import get_redis_client
    from app.ai.llm.models import AiModelConfig
    from sqlalchemy import select

    redis = await get_redis_client()

    stmt = select(AiModelConfig.id, AiModelConfig.name, AiModelConfig.provider)\
        .where(AiModelConfig.is_deleted == False)\
        .where(AiModelConfig.status == 1)
    result = await db.execute(stmt)
    model_configs = result.all()

    circuit_data = []
    for config in model_configs:
        model_config_id = config.id

        state_new = await redis.get(f"circuit:llm:{model_config_id}:state")
        state_old = await redis.get(f"llm:circuit:{model_config_id}:state")
        state = state_new or state_old or "closed"

        fail_count_new = await redis.get(f"circuit:llm:{model_config_id}:fail_count")
        fail_count_old = await redis.get(f"llm:circuit:{model_config_id}:fail_count")
        fail_count = int(fail_count_new or fail_count_old or "0")

        open_at_new = await redis.get(f"circuit:llm:{model_config_id}:open_at")
        open_at_old = await redis.get(f"llm:circuit:{model_config_id}:open_at")
        open_at = open_at_new or open_at_old

        data = {
            "circuit_type": "llm",
            "service_id": str(model_config_id),
            "model_config_id": model_config_id,
            "model_name": config.name,
            "provider": config.provider,
            "state": state.upper(),
            "fail_count": fail_count,
            "fail_threshold": 5,
            "open_timeout": 60,
        }

        if open_at:
            elapsed = int(time.time() - float(open_at))
            remaining = max(0, 60 - elapsed)
            data["open_at"] = int(float(open_at))
            data["elapsed_seconds"] = elapsed
            data["remaining_seconds"] = remaining

        circuit_data.append(data)

    return ok(circuit_data)


@router.post("/circuit/breakers/{circuit_type}/{service_id}/reset", summary="重置熔断器")
async def reset_circuit_breaker(
    circuit_type: str,
    service_id: str,
    current_user: Annotated[SysUser, Depends(require_permissions("monitor:circuit:reset"))],
):
    """
    手动重置指定服务的熔断器状态（强制关闭）。
    适用于：熔断器误触发、故障已修复需要立即恢复服务。
    
    circuit_type: llm / integration / websearch / codegen
    service_id: 服务标识（模型ID或集成ID）
    """
    from app.core.circuit_breaker import CircuitBreakerManager

    success = await CircuitBreakerManager.reset_breaker(circuit_type, service_id)
    if success:
        return ok(message="熔断器已重置")
    return ok(message="重置失败或熔断器不存在")


@router.post("/circuit/breakers/{circuit_type}/{service_id}/trip", summary="手动触发熔断")
async def trip_circuit_breaker(
    circuit_type: str,
    service_id: str,
    current_user: Annotated[SysUser, Depends(require_permissions("monitor:circuit:trip"))],
):
    """
    手动触发指定服务的熔断（强制打开）。
    适用于：外部服务即将维护、已知故障需要立即隔离。
    
    circuit_type: llm / integration / websearch / codegen
    service_id: 服务标识（模型ID或集成ID）
    """
    from app.core.circuit_breaker import CircuitBreakerManager

    success = await CircuitBreakerManager.trip_breaker(circuit_type, service_id)
    if success:
        return ok(message="熔断器已触发")
    return ok(message="触发失败")

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
    func_name: str | None = Query(None, description="Celery Task 完整路径"),
    status: int | None = Query(None, description="状态：1=启用 0=停用"),
):
    svc = TaskService(db)
    data = await svc.list_tasks(page_params, name=name, func_name=func_name, status=status)
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
