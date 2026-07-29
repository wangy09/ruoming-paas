"""
若茗 PaaS - Agent 相关 Pydantic Schema
Author: ruoming
"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ── Agent CRUD ────────────────────────────────────────────────────────────────

class AgentCreate(BaseModel):
    name: str = Field(..., max_length=64)
    description: str | None = None
    avatar: str | None = None
    model_config_id: int | None = None
    prompt_template_id: int | None = None
    prompt_version: int | None = None
    system_prompt: str | None = None
    default_scene: str | None = None
    max_rounds: int = Field(10, ge=1, le=50)
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(2048, ge=128, le=131072)
    node_timeout_sec: int = Field(60, ge=5, le=600)
    memory_type: str = Field("buffer", description="buffer / summary / vector / entity / kv")
    tool_ids: list[int] = Field(default_factory=list)
    kb_ids: list[int] = Field(default_factory=list)

    @field_validator("memory_type")
    @classmethod
    def validate_memory_type(cls, v: str) -> str:
        if v not in {"buffer", "summary", "vector", "entity", "kv"}:
            raise ValueError("memory_type 必须是 buffer / summary / vector / entity / kv 之一")
        return v


class AgentUpdate(BaseModel):
    name: str | None = Field(None, max_length=64)
    description: str | None = None
    system_prompt: str | None = None
    model_config_id: int | None = None
    prompt_template_id: int | None = None
    prompt_version: int | None = None
    temperature: float | None = Field(None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(None, ge=128, le=131072)
    tool_ids: list[int] | None = None
    kb_ids: list[int] | None = None
    status: int | None = Field(None, ge=0, le=1)
    default_scene: str | None = None


class AgentInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    avatar: str | None
    model_config_id: int | None
    prompt_template_id: int | None
    prompt_version: int | None
    system_prompt: str | None
    default_scene: str | None
    max_rounds: int
    temperature: float
    max_tokens: int
    memory_type: str
    tool_ids: list
    kb_ids: list
    status: int
    tenant_id: int | None
    created_at: datetime

    # 前端需要的扩展字段
    scene_label: str | None = None
    model_name: str | None = None
    tool_count: int | None = None
    kb_count: int | None = None
    memory_label: str | None = None
    node_timeout_sec: int | None = None


# ── Agent 执行 ────────────────────────────────────────────────────────────────

class AgentRunRequest(BaseModel):
    message: str = Field(..., description="用户消息")
    session_id: str | None = Field(None, description="会话 ID（不传则新建）")
    conversation_id: int | None = Field(None, description="关联已有对话 ID")
    stream: bool = Field(True, description="是否流式返回")
    scene_type: str | None = Field(None, description="显式指定场景类型")
    has_attachment: bool = Field(False, description="是否携带附件")
    timeout_sec: int | None = Field(None, ge=5, le=600)


class AgentRunResult(BaseModel):
    output: str
    conversation_id: int
    session_id: str
    scene: str | None = None
    scene_source: str | None = None
    total_tokens: int = 0
    latency_ms: int = 0
    intermediate_steps: list[Any] = Field(default_factory=list)


# ── 工作流 ────────────────────────────────────────────────────────────────────

class WorkflowCreate(BaseModel):
    name: str = Field(..., max_length=64)
    description: str | None = None
    graph_json: dict = Field(..., description="工作流图定义（nodes + edges）")
    trigger: str = Field("manual", description="触发方式：manual / api / schedule")
    changelog: str | None = Field(None, description="首版本变更说明")

    @field_validator("graph_json")
    @classmethod
    def validate_graph(cls, v: dict) -> dict:
        if "nodes" not in v or "edges" not in v:
            raise ValueError("graph_json 必须包含 nodes 和 edges 字段")
        return v


class WorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    graph_json: dict | None = None
    trigger: str | None = None
    changelog: str | None = None
    status: int | None = Field(None, ge=0, le=1)


class WorkflowInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    current_version: int
    trigger: str
    status: int
    tenant_id: int | None
    created_at: datetime


class WorkflowRunRequest(BaseModel):
    input: dict = Field(default_factory=dict, description="工作流输入参数")
    session_id: str | None = None


class WorkflowRunInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workflow_id: int
    workflow_version: int
    session_id: str | None
    status: str
    input: dict | None
    output: dict | None
    error: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
