"""
若茗 PaaS - Agent 和工作流路由
/agents
/workflows
Author: ruoming
"""
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, Query, Request
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
from app.core.rate_limit import limiter, get_user_key
from app.core.response import ApiResponse, PageData, created, ok, paged
from app.core.utils.pagination import PageParams
from app.database import get_db
from app.modules.user.models import SysUser

router = APIRouter(prefix="/ai", tags=["AI-Agent管理"])


# ── Agent CRUD ────────────────────────────────────────────────────────────────

SCENE_LABEL_MAP: dict[str, str] = {
    "chitchat": "闲聊",
    "professional": "专业分析",
    "task": "任务执行",
    "rag": "知识库问答",
    "creative": "创意写作",
}

MEMORY_LABEL_MAP: dict[str, str] = {
    "buffer": "全量",
    "summary": "摘要",
    "vector": "向量",
    "entity": "实体",
    "kv": "键值",
}


@router.get("/agents", summary="Agent 列表")
async def list_agents(
    keyword: str | None = Query(None, description="名称关键字"),
    page_params: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    from sqlalchemy import select
    from app.ai.llm.models import AiModelConfig

    svc = AgentService(db)
    items, total = await svc.get_list(current_user.tenant_id, page_params, keyword)

    model_ids = {a.model_config_id for a in items if a.model_config_id}
    model_map: dict[int, str] = {}
    if model_ids:
        result = await db.execute(
            select(AiModelConfig.id, AiModelConfig.name).where(AiModelConfig.id.in_(model_ids))
        )
        model_map = {row[0]: row[1] for row in result}

    enriched_items = []
    for agent in items:
        data = AgentInfo.model_validate(agent).model_dump()
        data["model_name"] = model_map.get(agent.model_config_id) if agent.model_config_id else None
        data["scene_label"] = SCENE_LABEL_MAP.get(agent.default_scene) if agent.default_scene else None
        data["memory_label"] = MEMORY_LABEL_MAP.get(agent.memory_type)
        data["tool_count"] = len(agent.tool_ids)
        data["kb_count"] = len(agent.kb_ids)
        enriched_items.append(data)

    return paged(items=enriched_items, total=total, page=page_params.page, page_size=page_params.page_size)


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
@limiter.limit("30/minute", key_func=get_user_key)
async def run_agent(
    agent_id: int,
    data: AgentRunRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """
    执行 Agent 推理。
    - stream=true：返回 SSE（text/event-stream）
    - stream=false：返回 JSON AgentRunResult
    响应中附带 scene 字段，方便前端展示推理场景来源。
    """
    import json
    from app.ai.conversation.service import ConversationService

    svc = AgentService(db)
    agent = await svc.get_by_id(agent_id)
    if not agent or agent.status != 1:
        raise NotFoundException(f"Agent ID={agent_id} 不存在或已禁用")

    conv_svc = ConversationService(db)

    # 获取或创建对话
    if data.conversation_id:
        from app.ai.conversation.models import AiConversation
        conv = await db.get(AiConversation, data.conversation_id)
        if not conv or conv.is_deleted or conv.user_id != current_user.id:
            conv = await conv_svc.create_conversation(
                user_id=current_user.id,
                tenant_id=current_user.tenant_id,
                agent_id=agent_id,
                title=data.message[:50],
            )
    else:
        conv = await conv_svc.create_conversation(
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            agent_id=agent_id,
            title=data.message[:50],
        )
    await db.commit()
    await db.refresh(conv)
    conv_id = conv.id

    # 加载对话历史作为记忆
    from app.core.utils.pagination import PageParams
    history_msgs, _ = await conv_svc.get_messages(conv_id, current_user.id, PageParams(page=1, page_size=200))
    conversation_history = [{"role": m.role, "content": m.content} for m in history_msgs]

    # 保存用户消息
    await conv_svc.add_message(conversation_id=conv_id, role="user", content=data.message)
    await db.commit()

    runner = AgentRunner(agent=agent, db=db)

    if data.stream:
        async def _generate() -> AsyncGenerator[str, None]:
            full_output = ""
            # 先把 conversation_id 告知前端
            yield f"data: {json.dumps({'type': 'meta', 'conversation_id': conv_id})}\n\n"
            async for event in runner.stream_run(
                user_message=data.message,
                session_id=data.session_id,
                conversation_history=conversation_history,
                scene_type=data.scene_type,
                has_attachment=data.has_attachment,
                timeout_sec=data.timeout_sec,
                tenant_id=current_user.tenant_id,
                user_id=current_user.id,
                conversation_id=conv_id,
            ):
                if event["type"] == "error":
                    yield f"data: {json.dumps(event)}\n\n"
                    break
                elif event["type"] == "meta":
                    yield f"data: {json.dumps(event)}\n\n"
                elif event["type"] == "content":
                    full_output += event.get("text", "")
                    yield f"data: {json.dumps({'type': 'content', 'text': event['text']})}\n\n"
                elif event["type"] == "done":
                    # 保存 assistant 消息
                    try:
                        from app.database import AsyncSessionFactory
                        async with AsyncSessionFactory() as save_db:
                            save_svc = ConversationService(save_db)
                            await save_svc.add_message(
                                conversation_id=conv_id,
                                role="assistant",
                                content=full_output or event.get("output", ""),
                            )
                            await save_db.commit()
                    except Exception:
                        pass
                    done_event = {"type": "done", "output": event.get("output", ""), "conversation_id": conv_id}
                    yield f"data: {json.dumps(done_event)}\n\n"

        return StreamingResponse(_generate(), media_type="text/event-stream")

    # 非流式
    result = await runner.run(
        user_message=data.message,
        session_id=data.session_id,
        conversation_history=conversation_history,
        scene_type=data.scene_type,
        has_attachment=data.has_attachment,
        timeout_sec=data.timeout_sec,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        conversation_id=conv_id,
    )
    # 保存 assistant 消息
    await conv_svc.add_message(
        conversation_id=conv_id,
        role="assistant",
        content=result.output,
        total_tokens=result.total_tokens,
        latency_ms=result.latency_ms,
    )
    await db.commit()
    result.conversation_id = conv_id
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
@limiter.limit("30/minute", key_func=get_user_key)
async def run_workflow(
    workflow_id: int,
    data: WorkflowRunRequest,
    request: Request,
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
