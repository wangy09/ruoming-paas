"""
若茗 PaaS - LLM 网关 Pydantic 模型
Author: ruoming
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ModelConfigCreate(BaseModel):
    """创建模型配置"""
    name: str = Field(..., max_length=64, description="配置名称")
    provider: str = Field(..., description="提供商：zhuilu / openai / ollama")
    model_id: str = Field(..., max_length=128, description="模型 ID")
    api_key: str | None = Field(None, description="API Key（明文，写入时自动加密）")
    base_url: str | None = Field(None, max_length=256, description="API 基础 URL")
    is_default: bool = Field(False, description="是否为默认对话模型")
    is_embed: bool = Field(False, description="是否为向量化专用模型")
    is_rerank: bool = Field(False, description="是否为 Rerank 模型")
    max_tokens: int = Field(4096, ge=128, le=131072, description="最大 Token 数")
    context_length: int = Field(8192, ge=512, description="上下文窗口长度")
    remark: str | None = None

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        allowed = {"zhuilu", "openai", "ollama", "azure"}
        if v not in allowed:
            raise ValueError(f"provider 必须是 {allowed} 之一")
        return v


class ModelConfigUpdate(BaseModel):
    """更新模型配置（全为可选）"""
    name: str | None = Field(None, max_length=64)
    api_key: str | None = None
    base_url: str | None = None
    is_default: bool | None = None
    is_embed: bool | None = None
    max_tokens: int | None = Field(None, ge=128, le=131072)
    remark: str | None = None
    status: int | None = Field(None, ge=0, le=1)


class ModelConfigInfo(BaseModel):
    """模型配置详情（对外不暴露 api_key 明文）"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    provider: str
    model_id: str
    base_url: str | None
    is_default: bool
    is_embed: bool
    is_rerank: bool
    max_tokens: int
    context_length: int
    remark: str | None
    status: int
    tenant_id: int | None
    created_at: datetime
    # api_key 故意不包含，接口不返回密文


class ChatRequest(BaseModel):
    """普通对话请求"""
    model_config_id: int | None = Field(None, description="模型配置 ID（不传则使用默认）")
    messages: list[dict] = Field(..., description="对话历史，格式：[{role, content}]")
    temperature: float | None = Field(None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(None, ge=1, le=131072)
    stream: bool = Field(True, description="是否流式返回")
    conversation_id: int | None = Field(None, description="关联已有对话 ID")


class ModelTestResult(BaseModel):
    """模型连通性测试结果"""
    success: bool
    latency_ms: int
    error: str | None = None
