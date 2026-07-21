"""
若茗 PaaS - 知识库相关 ORM 模型
Author: ruoming
"""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Float, Integer, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel
from app.database import Base


class AiKnowledgeBase(BaseModel):
    """
    AI 知识库主表（ai_knowledge_base）。
    支持多格式文档上传、向量化存储，提供混合检索（向量 + BM25 + Rerank）。
    """

    __tablename__ = "ai_knowledge_base"

    name: Mapped[str] = mapped_column(nullable=False, comment="知识库名称")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    embed_model_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="向量化模型配置 ID"
    )
    rerank_model_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="Rerank 模型配置 ID（可选）"
    )
    vector_store: Mapped[str] = mapped_column(
        default="pgvector", server_default="pgvector",
        comment="向量存储类型：pgvector / milvus / qdrant"
    )
    chunk_size: Mapped[int] = mapped_column(
        Integer, default=512, server_default="512", comment="分块大小（字符数）"
    )
    chunk_overlap: Mapped[int] = mapped_column(
        Integer, default=50, server_default="50", comment="分块重叠（字符数）"
    )
    retrieval_type: Mapped[str] = mapped_column(
        default="hybrid", server_default="hybrid",
        comment="检索类型：vector / bm25 / hybrid（默认混合检索）"
    )
    top_k: Mapped[int] = mapped_column(
        Integer, default=5, server_default="5", comment="返回最大结果数"
    )
    score_threshold: Mapped[float] = mapped_column(
        Float, default=0.5, server_default="0.5", comment="最低相关性阈值"
    )
    visibility: Mapped[str] = mapped_column(
        default="tenant", server_default="tenant",
        comment="可见范围：tenant（租户内全员）/ private（仅创建者）/ shared（指定用户/角色）"
    )
    status: Mapped[int] = mapped_column(SmallInteger, default=1, server_default="1")


class AiKnowledgeBaseShare(Base):
    """知识库共享配置表（ai_knowledge_base_share）"""

    __tablename__ = "ai_knowledge_base_share"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    kb_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(nullable=False, comment="共享目标类型：user / role")
    target_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default="NOW()")


class AiKnowledgeDoc(Base):
    """
    知识库文档表（ai_knowledge_doc）。
    content_hash 用于增量更新判断，避免重复索引未变化的文档。
    """

    __tablename__ = "ai_knowledge_doc"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    kb_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, comment="所属知识库 ID")
    name: Mapped[str] = mapped_column(nullable=False, comment="文档名称")
    source_type: Mapped[str | None] = mapped_column(
        nullable=True, comment="来源类型：file / url / text / notion / feishu"
    )
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True, comment="来源 URL")
    source_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True, comment="来源配置（API/数据库用）")
    file_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="关联文件存储 ID")
    file_type: Mapped[str | None] = mapped_column(nullable=True, comment="文件类型（扩展名）")
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="文件大小（字节）")
    storage_backend: Mapped[str | None] = mapped_column(
        nullable=True, comment="存储后端：local / oss / minio"
    )
    storage_key: Mapped[str | None] = mapped_column(
        nullable=True, comment="存储对象 key"
    )
    storage_url: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="存储访问 URL"
    )
    content_hash: Mapped[str | None] = mapped_column(
        nullable=True, comment="文件内容 SHA-256，用于增量更新"
    )
    char_count: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="字符数")
    chunk_count: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="分块数量")
    status: Mapped[str] = mapped_column(
        default="pending",
        comment="处理状态：pending / processing / done / error"
    )
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True, comment="处理错误信息")
    created_at: Mapped[datetime] = mapped_column(server_default="NOW()")
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


class AiKnowledgeChunk(Base):
    """
    知识库文档分块表（ai_knowledge_chunk）。
    每条记录对应一个文本块，存储原文 + 向量数据库中的 vector_id。
    """

    __tablename__ = "ai_knowledge_chunk"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    doc_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, comment="所属文档 ID")
    kb_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, comment="所属知识库 ID")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="分块文本内容")
    chunk_metadata: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", comment="块元数据")
    vector_id: Mapped[str | None] = mapped_column(nullable=True, comment="向量数据库中的 ID")
    chunk_index: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="块在文档中的序号")
    char_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default="NOW()")


class AiKnowledgeUploadPart(Base):
    """分片上传临时表（ai_knowledge_upload_part）"""

    __tablename__ = "ai_knowledge_upload_part"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    upload_id: Mapped[str] = mapped_column(nullable=False, index=True, comment="上传会话 ID（UUID）")
    kb_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    filename: Mapped[str] = mapped_column(nullable=False)
    file_hash: Mapped[str] = mapped_column(nullable=False, comment="完整文件 SHA-256")
    part_number: Mapped[int] = mapped_column(Integer, nullable=False, comment="分片序号（1-N）")
    part_size: Mapped[int] = mapped_column(Integer, nullable=False, comment="分片大小")
    part_hash: Mapped[str] = mapped_column(nullable=False, comment="分片 SHA-256")
    storage_key: Mapped[str] = mapped_column(nullable=False, comment="分片存储 key")
    created_at: Mapped[datetime] = mapped_column(server_default="NOW()")
    expires_at: Mapped[datetime] = mapped_column(nullable=False, comment="过期时间（24h）")


class AiKnowledgeTask(Base):
    """知识库任务状态表（ai_knowledge_task）"""

    __tablename__ = "ai_knowledge_task"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(nullable=False, unique=True, index=True, comment="Celery 任务 ID")
    kb_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, comment="所属知识库 ID")
    task_type: Mapped[str] = mapped_column(nullable=False, comment="任务类型：reindex_single / reindex_all")
    status: Mapped[str] = mapped_column(
        default="pending",
        comment="任务状态：pending / running / completed / failed"
    )
    total: Mapped[int] = mapped_column(Integer, default=0, comment="总任务数")
    completed: Mapped[int] = mapped_column(Integer, default=0, comment="已完成数")
    failed: Mapped[int] = mapped_column(Integer, default=0, comment="失败数")
    progress: Mapped[int] = mapped_column(Integer, default=0, comment="进度百分比")
    current_doc: Mapped[str | None] = mapped_column(nullable=True, comment="当前处理的文档名")
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True, comment="任务结果")
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True, comment="错误信息")
    created_at: Mapped[datetime] = mapped_column(server_default="NOW()")
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
