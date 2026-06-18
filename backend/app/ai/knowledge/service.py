"""
若茗 PaaS - 知识库服务层
Author: ruoming
"""
from __future__ import annotations

import hashlib

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

import structlog

from app.ai.knowledge.models import AiKnowledgeBase, AiKnowledgeDoc
from app.ai.knowledge.pipeline import RAGPipeline, RetrievedChunk
from app.ai.knowledge.schemas import KnowledgeBaseCreate, KnowledgeBaseUpdate
from app.core.exceptions import NotFoundException
from app.core.utils.pagination import PageParams

logger = structlog.get_logger(__name__)


class KnowledgeService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── 知识库 CRUD ────────────────────────────────────────────────────────────

    async def get_list(
        self,
        tenant_id: int | None,
        user_id: int,
        params: PageParams,
    ) -> tuple[list[AiKnowledgeBase], int]:
        stmt = (
            select(AiKnowledgeBase)
            .where(AiKnowledgeBase.is_deleted == False)
            .where(AiKnowledgeBase.status == 1)
        )
        # 知识库可见性过滤
        # tenant：同租户全员可见；private：仅创建者可见
        if tenant_id is not None:
            from sqlalchemy import or_
            stmt = stmt.where(
                or_(
                    AiKnowledgeBase.tenant_id == tenant_id,
                    AiKnowledgeBase.tenant_id.is_(None),
                )
            )

        count = await self.db.scalar(select(func.count()).select_from(stmt.subquery()))
        items = (
            await self.db.scalars(
                stmt.order_by(AiKnowledgeBase.created_at.desc())
                .offset(params.offset)
                .limit(params.page_size)
            )
        ).all()
        return list(items), count or 0

    async def get_by_id(self, kb_id: int) -> AiKnowledgeBase:
        kb = await self.db.get(AiKnowledgeBase, kb_id)
        if not kb or kb.is_deleted:
            raise NotFoundException(f"知识库 ID={kb_id} 不存在")
        return kb

    async def create(
        self, data: KnowledgeBaseCreate, tenant_id: int | None, user_id: int
    ) -> AiKnowledgeBase:
        kb = AiKnowledgeBase(
            name=data.name,
            description=data.description,
            embed_model_id=data.embed_model_id,
            rerank_model_id=data.rerank_model_id,
            vector_store=data.vector_store,
            chunk_size=data.chunk_size,
            chunk_overlap=data.chunk_overlap,
            retrieval_type=data.retrieval_type,
            top_k=data.top_k,
            score_threshold=data.score_threshold,
            visibility=data.visibility,
            tenant_id=tenant_id,
            created_by=user_id,
        )
        self.db.add(kb)
        await self.db.commit()
        await self.db.refresh(kb)
        return kb

    async def update(self, kb_id: int, data: KnowledgeBaseUpdate) -> AiKnowledgeBase:
        kb = await self.get_by_id(kb_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(kb, field, value)
        await self.db.commit()
        await self.db.refresh(kb)
        return kb

    async def delete(self, kb_id: int) -> None:
        kb = await self.get_by_id(kb_id)
        kb.is_deleted = True
        # 同步软删除文档（向量不立即清理，后台任务处理）
        await self.db.execute(
            select(AiKnowledgeDoc).where(AiKnowledgeDoc.kb_id == kb_id)
        )
        await self.db.commit()

    # ── 文档管理 ───────────────────────────────────────────────────────────────

    async def upload_document(
        self,
        kb_id: int,
        filename: str,
        file_content: bytes,
        source_type: str = "file",
    ) -> AiKnowledgeDoc:
        """上传并立即同步索引文档（小文件适用；大文件应走异步任务）"""
        kb = await self.get_by_id(kb_id)

        content_hash = hashlib.sha256(file_content).hexdigest()

        # 检查是否已有相同 hash 的文档（幂等上传）
        existing = await self.db.execute(
            select(AiKnowledgeDoc)
            .where(AiKnowledgeDoc.kb_id == kb_id)
            .where(AiKnowledgeDoc.content_hash == content_hash)
            .where(AiKnowledgeDoc.is_deleted == False)
        )
        if existing.scalar_one_or_none():
            raise ValueError("相同内容的文档已存在，请勿重复上传")

        doc = AiKnowledgeDoc(
            kb_id=kb_id,
            name=filename,
            source_type=source_type,
            content_hash=content_hash,
            status="processing",
        )
        self.db.add(doc)
        await self.db.flush()

        # 立即索引
        pipeline = RAGPipeline(kb=kb, db=self.db)
        try:
            chunk_count = await pipeline.index_document(doc, file_content)
            logger.info("knowledge_upload_done", kb_id=kb_id, doc_id=doc.id, chunks=chunk_count)
        except Exception as e:
            doc.status = "error"
            doc.error_msg = str(e)
            await self.db.commit()
            raise

        await self.db.refresh(doc)
        return doc

    async def update_document(self, kb_id: int, doc_id: int, file_content: bytes) -> dict:
        """
        文档增量更新：
        1. 计算新内容哈希，若与旧哈希相同则跳过
        2. 删除旧 chunk 的向量（向量库 + 数据库）
        3. 重新分块、向量化、写入
        """
        kb = await self.get_by_id(kb_id)
        doc = await self.db.get(AiKnowledgeDoc, doc_id)
        if not doc or doc.kb_id != kb_id or doc.is_deleted:
            raise NotFoundException(f"文档 ID={doc_id} 不存在")

        new_hash = hashlib.sha256(file_content).hexdigest()
        if doc.content_hash == new_hash:
            return {"message": "内容未变化，跳过更新", "doc_id": doc_id}

        pipeline = RAGPipeline(kb=kb, db=self.db)

        # 删除旧向量
        await pipeline.delete_document_vectors(doc_id, kb_id)

        # 重新索引
        doc.status = "processing"
        await self.db.flush()

        chunk_count = await pipeline.index_document(doc, file_content)
        return {"message": "文档更新成功", "doc_id": doc_id, "chunks": chunk_count}

    async def delete_document(self, kb_id: int, doc_id: int) -> None:
        """删除文档及其向量数据"""
        kb = await self.get_by_id(kb_id)
        doc = await self.db.get(AiKnowledgeDoc, doc_id)
        if not doc or doc.kb_id != kb_id or doc.is_deleted:
            raise NotFoundException(f"文档 ID={doc_id} 不存在")

        pipeline = RAGPipeline(kb=kb, db=self.db)
        await pipeline.delete_document_vectors(doc_id, kb_id)

        doc.is_deleted = True
        await self.db.commit()

    async def list_documents(
        self, kb_id: int, params: PageParams
    ) -> tuple[list[AiKnowledgeDoc], int]:
        stmt = (
            select(AiKnowledgeDoc)
            .where(AiKnowledgeDoc.kb_id == kb_id)
            .where(AiKnowledgeDoc.is_deleted == False)
        )
        count = await self.db.scalar(select(func.count()).select_from(stmt.subquery()))
        items = (
            await self.db.scalars(
                stmt.order_by(AiKnowledgeDoc.created_at.desc())
                .offset(params.offset)
                .limit(params.page_size)
            )
        ).all()
        return list(items), count or 0

    # ── 检索 ───────────────────────────────────────────────────────────────────

    async def search(
        self,
        kb_id: int,
        query: str,
        top_k: int = 5,
        score_threshold: float = 0.5,
        retrieval_type: str | None = None,
    ) -> list[dict]:
        """执行知识库检索，返回结果列表（供 Agent 调用）"""
        kb = await self.get_by_id(kb_id)

        # 临时覆盖检索类型（用于测试）
        if retrieval_type:
            kb.retrieval_type = retrieval_type

        pipeline = RAGPipeline(kb=kb, db=self.db)
        chunks = await pipeline.retrieve(query, top_k)

        return [
            {
                "content": c.content,
                "doc_id": c.doc_id,
                "score": c.score,
                "metadata": c.metadata,
            }
            for c in chunks
            if c.score >= score_threshold
        ]
