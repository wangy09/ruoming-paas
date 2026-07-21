"""
若茗 PaaS - Agent 相关 ORM 模型
Author: ruoming
"""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Float, Integer, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel
from app.database import Base


class AiAgent(BaseModel):
    """
    AI Agent 定义表（ai_agent）。
    每个 Agent 独立配置：系统提示词、绑定模型、工具列表、知识库列表、场景路由等。
    """

    __tablename__ = "ai_agent"

    name: Mapped[str] = mapped_column(nullable=False, comment="Agent 名称")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Agent 描述")
    avatar: Mapped[str | None] = mapped_column(nullable=True, comment="头像 URL")
    model_config_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="绑定的 LLM 模型配置 ID"
    )
    # Prompt 版本化：优先使用 prompt_template_id，其次使用 system_prompt 文本
    prompt_template_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="Prompt 模板 ID（优先级高于 system_prompt）"
    )
    prompt_version: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Prompt 版本号（NULL=最新已发布版本）"
    )
    system_prompt: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="系统提示词（prompt_template_id 为空时使用）"
    )
    default_scene: Mapped[str | None] = mapped_column(
        nullable=True, comment="默认场景类型：chitchat / professional / task / rag / creative"
    )
    max_rounds: Mapped[int] = mapped_column(
        Integer, default=10, server_default="10", comment="最大对话轮次"
    )
    temperature: Mapped[float] = mapped_column(
        Float, default=0.7, server_default="0.7", comment="生成温度"
    )
    max_tokens: Mapped[int] = mapped_column(
        Integer, default=2048, server_default="2048", comment="最大输出 Token 数"
    )
    node_timeout_sec: Mapped[int] = mapped_column(
        Integer, default=60, server_default="60", comment="单次推理超时（秒）"
    )
    memory_type: Mapped[str] = mapped_column(
        default="buffer", server_default="buffer",
        comment="记忆类型：buffer（全量）/ summary（摘要）/ vector（向量）"
    )
    tool_ids: Mapped[list] = mapped_column(
        JSONB, default=list, server_default="[]", comment="可用工具 ID 列表"
    )
    kb_ids: Mapped[list] = mapped_column(
        JSONB, default=list, server_default="[]", comment="关联知识库 ID 列表"
    )
    status: Mapped[int] = mapped_column(
        SmallInteger, default=1, server_default="1", comment="状态：1=启用，0=禁用"
    )


class AiSceneConfig(Base):
    """
    AI 场景配置表（ai_scene_config）。
    每个 Agent 可为每种场景单独配置 Prompt / temperature / 模型，覆盖 Agent 默认值。
    """

    __tablename__ = "ai_scene_config"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    agent_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, index=True, comment="Agent ID（NULL=全局默认场景配置）"
    )
    scene_type: Mapped[str] = mapped_column(
        nullable=False, comment="场景类型：chitchat / professional / task / rag / creative"
    )
    model_config_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="场景专用模型（NULL=继承 Agent 默认）"
    )
    prompt_template_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    prompt_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True, comment="场景专用 system prompt")
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True, comment="NULL=继承 Agent 默认")
    max_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    enable_rag: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", comment="是否开启 RAG 检索"
    )
    rag_top_k: Mapped[int] = mapped_column(Integer, default=5, server_default="5")
    rag_score_threshold: Mapped[float] = mapped_column(Float, default=0.5, server_default="0.5")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    tenant_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default="NOW()")
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class AiWorkflow(BaseModel):
    """
    AI 工作流主表（ai_workflow）。
    工作流使用有向图（含受控回退循环）。图结构版本化存储在 AiWorkflowVersion 中。
    """

    __tablename__ = "ai_workflow"

    name: Mapped[str] = mapped_column(nullable=False, comment="工作流名称")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_version: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", comment="当前生效版本号"
    )
    trigger: Mapped[str] = mapped_column(
        default="manual", server_default="manual",
        comment="触发方式：manual / api / schedule"
    )
    status: Mapped[int] = mapped_column(SmallInteger, default=1, server_default="1")


class AiWorkflowVersion(Base):
    """工作流版本快照表（ai_workflow_version）"""

    __tablename__ = "ai_workflow_version"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    workflow_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, comment="版本号（递增）")
    graph_json: Mapped[dict] = mapped_column(JSONB, nullable=False, comment="图定义 JSON")
    changelog: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default="NOW()")


class AiWorkflowRun(Base):
    """工作流执行记录表（ai_workflow_run）"""

    __tablename__ = "ai_workflow_run"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    workflow_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    workflow_version: Mapped[int] = mapped_column(Integer, nullable=False, comment="执行时的版本号（历史可追溯）")
    session_id: Mapped[str | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(
        default="pending",
        comment="状态：pending / running / success / failed / timeout"
    )
    input: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    tenant_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True, comment="租户 ID（用于多租户隔离）")
    created_at: Mapped[datetime] = mapped_column(server_default="NOW()")


class AiWorkflowNodeRun(Base):
    """工作流节点执行明细表（ai_workflow_node_run）"""

    __tablename__ = "ai_workflow_node_run"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, comment="关联 ai_workflow_run.id")
    node_id: Mapped[str] = mapped_column(nullable=False, comment="图中节点 ID")
    node_type: Mapped[str | None] = mapped_column(nullable=True, comment="节点类型：agent / tool / condition / start / end / parallel")
    status: Mapped[str | None] = mapped_column(nullable=True)
    iteration: Mapped[int] = mapped_column(Integer, default=1, server_default="1", comment="循环场景下的第几次执行")
    input: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
