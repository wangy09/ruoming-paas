"""
若茗 PaaS - Agent 服务层
Author: ruoming
"""
from __future__ import annotations

import uuid
from datetime import datetime, UTC

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agent.models import AiAgent, AiWorkflow, AiWorkflowVersion, AiWorkflowRun
from app.ai.agent.schemas import AgentCreate, AgentUpdate, WorkflowCreate, WorkflowUpdate
from app.core.utils.pagination import PageParams


class AgentService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Agent CRUD ─────────────────────────────────────────────────────────

    async def get_list(
        self,
        tenant_id: int | None,
        params: PageParams,
        keyword: str | None = None,
    ) -> tuple[list[AiAgent], int]:
        from app.ai.llm.models import AiModelConfig

        stmt = (
            select(AiAgent)
            .outerjoin(AiModelConfig, AiAgent.model_config_id == AiModelConfig.id)
            .where(AiAgent.is_deleted == False)
        )
        if tenant_id is not None:
            stmt = stmt.where(AiAgent.tenant_id == tenant_id)
        if keyword:
            stmt = stmt.where(AiAgent.name.ilike(f"%{keyword}%"))

        count = await self.db.scalar(select(func.count()).select_from(stmt.subquery()))
        items = (
            await self.db.scalars(
                stmt.order_by(AiAgent.created_at.desc())
                .offset(params.offset)
                .limit(params.page_size)
            )
        ).all()
        return list(items), count or 0

    async def get_by_id(self, agent_id: int, tenant_id: int | None = None) -> AiAgent | None:
        stmt = select(AiAgent).where(AiAgent.id == agent_id, AiAgent.is_deleted == False)
        if tenant_id is not None:
            stmt = stmt.where(AiAgent.tenant_id == tenant_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        data: AgentCreate,
        tenant_id: int | None,
        user_id: int,
    ) -> AiAgent:
        agent = AiAgent(
            name=data.name,
            description=data.description,
            avatar=data.avatar,
            model_config_id=data.model_config_id,
            system_prompt=data.system_prompt,
            default_scene=data.default_scene,
            max_rounds=data.max_rounds,
            temperature=data.temperature,
            max_tokens=data.max_tokens,
            node_timeout_sec=data.node_timeout_sec,
            memory_type=data.memory_type,
            tool_ids=data.tool_ids,
            kb_ids=data.kb_ids,
            tenant_id=tenant_id,
            created_by=user_id,
        )
        self.db.add(agent)
        await self.db.commit()
        await self.db.refresh(agent)
        return agent

    async def update(self, agent_id: int, data: AgentUpdate, tenant_id: int | None = None) -> AiAgent | None:
        agent = await self.get_by_id(agent_id, tenant_id)
        if not agent:
            return None

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(agent, field, value)

        await self.db.commit()
        await self.db.refresh(agent)
        return agent

    async def delete(self, agent_id: int, tenant_id: int | None = None) -> bool:
        agent = await self.get_by_id(agent_id, tenant_id)
        if not agent:
            return False
        agent.is_deleted = True
        await self.db.commit()
        return True


class WorkflowService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_list(
        self,
        tenant_id: int | None,
        params: PageParams,
    ) -> tuple[list[AiWorkflow], int]:
        stmt = select(AiWorkflow).where(AiWorkflow.is_deleted == False)
        if tenant_id is not None:
            stmt = stmt.where(AiWorkflow.tenant_id == tenant_id)

        count = await self.db.scalar(select(func.count()).select_from(stmt.subquery()))
        items = (
            await self.db.scalars(
                stmt.order_by(AiWorkflow.created_at.desc())
                .offset(params.offset)
                .limit(params.page_size)
            )
        ).all()
        return list(items), count or 0

    async def create(
        self, data: WorkflowCreate, tenant_id: int | None, user_id: int
    ) -> AiWorkflow:
        workflow = AiWorkflow(
            name=data.name,
            description=data.description,
            trigger=data.trigger,
            current_version=1,
            tenant_id=tenant_id,
            created_by=user_id,
        )
        self.db.add(workflow)
        await self.db.flush()

        # 建立 v1 版本快照
        version = AiWorkflowVersion(
            workflow_id=workflow.id,
            version=1,
            graph_json=data.graph_json,
            changelog=data.changelog or "初始版本",
            created_by=user_id,
        )
        self.db.add(version)
        await self.db.commit()
        await self.db.refresh(workflow)
        return workflow

    async def update(self, workflow_id: int, data: WorkflowUpdate, user_id: int, tenant_id: int | None = None) -> AiWorkflow | None:
        stmt = select(AiWorkflow).where(AiWorkflow.id == workflow_id, AiWorkflow.is_deleted == False)
        if tenant_id is not None:
            stmt = stmt.where(AiWorkflow.tenant_id == tenant_id)
        result = await self.db.execute(stmt)
        workflow = result.scalar_one_or_none()
        if not workflow:
            return None

        # 若更新了图结构，新增版本快照
        if data.graph_json:
            new_version = workflow.current_version + 1
            version = AiWorkflowVersion(
                workflow_id=workflow_id,
                version=new_version,
                graph_json=data.graph_json,
                changelog=data.changelog or f"版本 {new_version}",
                created_by=user_id,
            )
            self.db.add(version)
            workflow.current_version = new_version

        for field, value in data.model_dump(exclude_unset=True, exclude={"graph_json", "changelog"}).items():
            setattr(workflow, field, value)

        await self.db.commit()
        await self.db.refresh(workflow)
        return workflow

    async def get_versions(self, workflow_id: int) -> list[AiWorkflowVersion]:
        result = await self.db.execute(
            select(AiWorkflowVersion)
            .where(AiWorkflowVersion.workflow_id == workflow_id)
            .order_by(AiWorkflowVersion.version.desc())
        )
        return list(result.scalars().all())

    async def get_current_graph(self, workflow_id: int) -> dict | None:
        workflow = await self.db.get(AiWorkflow, workflow_id)
        if not workflow:
            return None
        result = await self.db.execute(
            select(AiWorkflowVersion)
            .where(AiWorkflowVersion.workflow_id == workflow_id)
            .where(AiWorkflowVersion.version == workflow.current_version)
        )
        version = result.scalar_one_or_none()
        return version.graph_json if version else None

    async def run_workflow(
        self,
        workflow_id: int,
        input_data: dict,
        session_id: str | None,
        user_id: int,
        tenant_id: int | None = None,
    ) -> AiWorkflowRun:
        workflow = await self.db.get(AiWorkflow, workflow_id)
        if not workflow or workflow.is_deleted:
            from app.core.exceptions import NotFoundException
            raise NotFoundException(f"工作流 ID={workflow_id} 不存在")

        graph_json = await self.get_current_graph(workflow_id)
        if not graph_json:
            from app.core.exceptions import AppException
            raise AppException(message="工作流图定义不存在")

        sid = session_id or str(uuid.uuid4())

        # 先创建 pending 状态的运行记录
        run = AiWorkflowRun(
            workflow_id=workflow_id,
            workflow_version=workflow.current_version,
            session_id=sid,
            status="pending",
            input=input_data,
            started_at=datetime.now(UTC),
            created_by=user_id,
            tenant_id=tenant_id,
        )
        self.db.add(run)
        await self.db.flush()  # 获取 run.id，但不提交

        # 先执行 AI 调用（可能在 flush 之后但 commit 之前失败）
        output: dict = {}
        error_msg: str | None = None

        try:
            from app.ai.agent.executor import WorkflowOrchestrator
            orchestrator = WorkflowOrchestrator(graph_json=graph_json, db=self.db)
            output = await orchestrator.run(input_data=input_data, run_id=run.id)

            # 成功时更新状态并提交
            run.status = "success"
            run.output = output
            run.finished_at = datetime.now(UTC)
            await self.db.commit()
            await self.db.refresh(run)
            return run
        except Exception as e:
            import traceback as tb
            error_msg = f"{str(e)}\n{tb.format_exc()}"

            # 失败时回滚事务，不保留记录
            await self.db.rollback()

            # 重新创建失败记录并提交（用于问题追踪）
            failed_run = AiWorkflowRun(
                workflow_id=workflow_id,
                workflow_version=workflow.current_version,
                session_id=sid,
                status="failed",
                input=input_data,
                output={},
                error=error_msg,
                started_at=datetime.now(UTC),
                finished_at=datetime.now(UTC),
                created_by=user_id,
                tenant_id=tenant_id,
            )
            self.db.add(failed_run)
            await self.db.commit()
            await self.db.refresh(failed_run)
            return failed_run

    async def get_runs(
        self, workflow_id: int, params: PageParams
    ) -> tuple[list[AiWorkflowRun], int]:
        stmt = select(AiWorkflowRun).where(AiWorkflowRun.workflow_id == workflow_id)
        count = await self.db.scalar(select(func.count()).select_from(stmt.subquery()))
        items = (
            await self.db.scalars(
                stmt.order_by(AiWorkflowRun.created_at.desc())
                .offset(params.offset)
                .limit(params.page_size)
            )
        ).all()
        return list(items), count or 0
