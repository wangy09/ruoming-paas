"""
若茗 PaaS - Prompt 模板 Pydantic Schema
Author: ruoming
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PromptTemplateCreate(BaseModel):
    name: str = Field(..., max_length=64)
    description: str | None = None
    category: str | None = Field(None, description="system / user / few-shot / chain")
    variables: list[str] = Field(default_factory=list, description="模板变量名列表")
    content: str = Field(..., description="初始版本内容（支持 {{variable}} 插值）")
    changelog: str | None = Field(None, description="v1 版本变更说明")


class PromptVersionCreate(BaseModel):
    content: str = Field(..., description="新版本内容")
    changelog: str | None = None


class PromptTemplateInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    category: str | None
    current_version: int
    variables: list
    status: int
    tenant_id: int | None
    created_at: datetime


class PromptVersionInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    template_id: int
    version: int
    content: str
    changelog: str | None
    eval_score: float | None
    is_published: bool
    created_at: datetime


class PromptRenderRequest(BaseModel):
    variables: dict = Field(default_factory=dict, description="变量键值对，用于预览渲染结果")
    version: int | None = Field(None, description="指定版本号（不传则使用当前版本）")
