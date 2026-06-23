"""
若茗 PaaS - 知识库 Pydantic Schema
Author: ruoming
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(..., max_length=64)
    description: str | None = None
    embed_model_id: int | None = None
    rerank_model_id: int | None = None
    vector_store: str = Field("pgvector", description="pgvector / milvus / qdrant")
    chunk_size: int = Field(512, ge=64, le=4096)
    chunk_overlap: int = Field(50, ge=0, le=512)
    retrieval_type: str = Field("hybrid", description="vector / bm25 / hybrid")
    top_k: int = Field(5, ge=1, le=20)
    score_threshold: float = Field(0.5, ge=0.0, le=1.0)
    visibility: str = Field("tenant", description="tenant / private / shared")

    @field_validator("retrieval_type")
    @classmethod
    def validate_retrieval_type(cls, v: str) -> str:
        if v not in {"vector", "bm25", "hybrid"}:
            raise ValueError("retrieval_type 必须是 vector / bm25 / hybrid 之一")
        return v


class KnowledgeBaseUpdate(BaseModel):
    name: str | None = Field(None, max_length=64)
    description: str | None = None
    chunk_size: int | None = Field(None, ge=64, le=4096)
    chunk_overlap: int | None = Field(None, ge=0, le=512)
    retrieval_type: str | None = None
    top_k: int | None = Field(None, ge=1, le=20)
    score_threshold: float | None = Field(None, ge=0.0, le=1.0)
    status: int | None = Field(None, ge=0, le=1)


class KnowledgeBaseInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    embed_model_id: int | None
    rerank_model_id: int | None
    vector_store: str
    chunk_size: int
    chunk_overlap: int
    retrieval_type: str
    top_k: int
    score_threshold: float
    visibility: str
    status: int
    tenant_id: int | None
    created_at: datetime


class KnowledgeDocInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kb_id: int
    name: str
    source_type: str | None
    source_url: str | None
    file_type: str | None
    file_size: int | None
    storage_backend: str | None
    storage_url: str | None
    content_hash: str | None
    char_count: int | None
    chunk_count: int | None
    status: str
    error_msg: str | None
    created_at: datetime


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(..., description="检索查询词")
    top_k: int = Field(5, ge=1, le=20)
    retrieval_type: str | None = Field(None, description="覆盖知识库默认检索类型")


class KnowledgeSearchResult(BaseModel):
    content: str
    doc_id: int
    score: float
    metadata: dict = Field(default_factory=dict)


# ── 分片上传 ────────────────────────────────────────────────────────────────

class UploadInitRequest(BaseModel):
    filename: str = Field(..., max_length=255)
    file_size: int = Field(..., ge=1, description="文件总大小（字节）")
    file_hash: str = Field(..., description="完整文件 SHA-256")
    part_count: int = Field(..., ge=1, description="分片总数")


class UploadInitResponse(BaseModel):
    upload_id: str = Field(..., description="上传会话 ID")
    part_size: int = Field(..., description="每个分片大小（字节）")
    uploaded_parts: list[int] = Field(default_factory=list, description="已上传的分片序号")


class UploadPartRequest(BaseModel):
    upload_id: str
    part_number: int = Field(..., ge=1)
    part_hash: str = Field(..., description="分片 SHA-256")


class UploadCompleteRequest(BaseModel):
    upload_id: str
    part_hashes: list[str] = Field(..., description="所有分片 hash 列表（按序号排序）")
