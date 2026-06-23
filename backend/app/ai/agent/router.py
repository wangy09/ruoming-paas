"""
若茗 PaaS - Agent 和工作流路由
/agents
/workflows
Author: ruoming
"""
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agent.executor import AgentRunner
from app.ai.agent.schemas import (
    AgentCreate,
    AgentInfo,
    AgentRunRequest,
    AgentRunResult,
    WorkflowCreate,
    WorkflowInfo,
    WorkflowRunInfo,
    WorkflowRunRequest,
    WorkflowUpdate,
)
from app.ai.agent.service import AgentService, WorkflowService
from app.core.deps import get_current_user, require_permissions
from app.core.exceptions import NotFoundException
from app.core.response import ApiResponse, PageData, created, ok, paged
from app.core.utils.pagination import PageParams
from app.database import get_db
from app.modules.user.models import SysUser

router = APIRouter(prefix="/ai", tags=["AI-Agent管理"])


# ── Agent CRUD ────────────────────────────────────────────────────────────────

@router.get("/agents", response_model=ApiResponse[PageData[AgentInfo]], summary="Agent 列表")
async def list_agents(
    keyword: str | None = Query(None, description="名称关键字"),
    page_params: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    svc = AgentService(db)
    items, total = await svc.get_list(current_user.tenant_id, page_params, keyword)
    return paged(items=[AgentInfo.model_validate(i) for i in items], total=total, page=page_params.page, page_size=page_params.page_size)


@router.post("/agents", response_model=ApiResponse[AgentInfo], summary="创建 Agent", status_code=201)
async def create_agent(
    data: AgentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: SysUser = Depends(require_permissions("ai:agent:create")),
):
    svc = AgentService(db)
    agent = await svc.create(data, current_user.tenant_id, current_user.id)
    return created(AgentInfo.model_validate(agent))


@router.put("/agents/{agent_id}", response_model=ApiResponse[AgentInfo], summary="修改 Agent")
async def update_agent(
    agent_id: int,
    data: AgentCreate,
    db: AsyncSession = Depends(get_db),
    _: SysUser = Depends(require_permissions("ai:agent:update")),
):
    from app.ai.agent.schemas import AgentUpdate
    svc = AgentService(db)
    agent = await svc.update(agent_id, AgentUpdate(**data.model_dump(exclude_unset=True)))
    if not agent:
        raise NotFoundException(f"Agent ID={agent_id} 不存在")
    return ok(AgentInfo.model_validate(agent))


@router.delete("/agents/{agent_id}", response_model=ApiResponse, summary="删除 Agent")
async def delete_agent(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
    _: SysUser = Depends(require_permissions("ai:agent:delete")),
):
    svc = AgentService(db)
    if not await svc.delete(agent_id):
        raise NotFoundException(f"Agent ID={agent_id} 不存在")
    return ok(message="删除成功")


# ── Agent 执行 ────────────────────────────────────────────────────────────────

@router.post("/agents/{agent_id}/run", summary="执行 Agent（支持流式 SSE）")
async def run_agent(
    agent_id: int,
    data: AgentRunRequest,
    db: AsyncSession = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """
    执行 Agent 推理。
    - stream=true：返回 SSE（text/event-stream）
    - stream=false：返回 JSON AgentRunResult
    响应中附带 scene 字段，方便前端展示推理场景来源。
    """
    svc = AgentService(db)
    agent = await svc.get_by_id(agent_id)
    if not agent or agent.status != 1:
        raise NotFoundException(f"Agent ID={agent_id} 不存在或已禁用")

    runner = AgentRunner(agent=agent, db=db)

    if data.stream:
        async def _generate() -> AsyncGenerator[str, None]:
            import json
            async for event in runner.stream_run(
                user_message=data.message,
                session_id=data.session_id,
                scene_type=data.scene_type,
                has_attachment=data.has_attachment,
                timeout_sec=data.timeout_sec,
                tenant_id=current_user.tenant_id,
                user_id=current_user.id,
                conversation_id=data.conversation_id,
            ):
                if event["type"] == "error":
                    yield f"data: {json.dumps(event)}\n\n"
                    break
                elif event["type"] == "meta":
                    yield f"data: {json.dumps(event)}\n\n"
                elif event["type"] == "content":
                    yield f"data: {json.dumps({'type': 'content', 'text': event['text']})}\n\n"
                elif event["type"] == "done":
                    done_event = {"type": "done", "output": event.get("output", "")}
                    yield f"data: {json.dumps(done_event)}\n\n"

        return StreamingResponse(_generate(), media_type="text/event-stream")

    # 非流式
    result = await runner.run(
        user_message=data.message,
        session_id=data.session_id,
        scene_type=data.scene_type,
        has_attachment=data.has_attachment,
        timeout_sec=data.timeout_sec,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        conversation_id=data.conversation_id,
    )
    return ok(result)


# ── 工作流 CRUD ───────────────────────────────────────────────────────────────

@router.get("/workflows", response_model=ApiResponse[PageData[WorkflowInfo]], summary="工作流列表")
async def list_workflows(
    page_params: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    svc = WorkflowService(db)
    items, total = await svc.get_list(current_user.tenant_id, page_params)
    return paged(items=[WorkflowInfo.model_validate(i) for i in items], total=total, page=page_params.page, page_size=page_params.page_size)


@router.post("/workflows", response_model=ApiResponse[WorkflowInfo], summary="创建工作流", status_code=201)
async def create_workflow(
    data: WorkflowCreate,
    db: AsyncSession = Depends(get_db),
    current_user: SysUser = Depends(require_permissions("ai:workflow:create")),
):
    svc = WorkflowService(db)
    workflow = await svc.create(data, current_user.tenant_id, current_user.id)
    return created(WorkflowInfo.model_validate(workflow))


@router.put("/workflows/{workflow_id}", response_model=ApiResponse[WorkflowInfo], summary="修改工作流（自动新增版本）")
async def update_workflow(
    workflow_id: int,
    data: WorkflowUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: SysUser = Depends(require_permissions("ai:workflow:update")),
):
    svc = WorkflowService(db)
    workflow = await svc.update(workflow_id, data, current_user.id)
    if not workflow:
        raise NotFoundException(f"工作流 ID={workflow_id} 不存在")
    return ok(WorkflowInfo.model_validate(workflow))


@router.get("/workflows/{workflow_id}/versions", response_model=ApiResponse, summary="工作流版本历史")
async def get_workflow_versions(
    workflow_id: int,
    db: AsyncSession = Depends(get_db),
    _: SysUser = Depends(get_current_user),
):
    svc = WorkflowService(db)
    versions = await svc.get_versions(workflow_id)
    return ok([
        {
            "version": v.version,
            "changelog": v.changelog,
            "created_at": v.created_at.isoformat(),
            "graph_json": v.graph_json,
        }
        for v in versions
    ])


@router.post("/workflows/{workflow_id}/run", response_model=ApiResponse[WorkflowRunInfo], summary="执行工作流")
async def run_workflow(
    workflow_id: int,
    data: WorkflowRunRequest,
    db: AsyncSession = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    svc = WorkflowService(db)
    run = await svc.run_workflow(
        workflow_id=workflow_id,
        input_data=data.input,
        session_id=data.session_id,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
    )
    return ok(WorkflowRunInfo.model_validate(run))


@router.get("/workflows/{workflow_id}/runs", response_model=ApiResponse[PageData[WorkflowRunInfo]], summary="执行历史")
async def get_workflow_runs(
    workflow_id: int,
    page_params: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
    _: SysUser = Depends(get_current_user),
):
    svc = WorkflowService(db)
    items, total = await svc.get_runs(workflow_id, page_params)
    return paged(items=[WorkflowRunInfo.model_validate(i) for i in items], total=total, page=page_params.page, page_size=page_params.page_size)
