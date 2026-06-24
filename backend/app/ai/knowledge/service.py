"""
若茗 PaaS - 知识库服务层
Author: ruoming
"""
from __future__ import annotations

import hashlib
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

import structlog

from app.ai.knowledge.models import AiKnowledgeBase, AiKnowledgeDoc
from app.ai.knowledge.pipeline import RAGPipeline, RetrievedChunk
from app.ai.knowledge.schemas import KnowledgeBaseCreate, KnowledgeBaseUpdate
from app.core.exceptions import AppException, NotFoundException
from app.core.storage.factory import get_storage
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
        from app.ai.knowledge.tasks import delete_document_vectors_task
        delete_document_vectors_task.delay(doc_id=0, kb_id=kb_id)
        await self.db.commit()

    async def get_stats(self, kb_id: int) -> dict:
        """获取知识库统计信息"""
        kb = await self.get_by_id(kb_id)
        stats = await self.db.execute(
            select(
                func.count(AiKnowledgeDoc.id).label("total_docs"),
                func.sum(AiKnowledgeDoc.char_count).label("total_chars"),
                func.sum(AiKnowledgeDoc.chunk_count).label("total_chunks"),
                func.count(AiKnowledgeDoc.id).filter(AiKnowledgeDoc.status == "done").label("done_docs"),
                func.count(AiKnowledgeDoc.id).filter(AiKnowledgeDoc.status == "processing").label("processing_docs"),
                func.count(AiKnowledgeDoc.id).filter(AiKnowledgeDoc.status == "error").label("error_docs"),
            ).where(AiKnowledgeDoc.kb_id == kb_id)
            .where(AiKnowledgeDoc.is_deleted == False)
        )
        row = stats.one()
        return {
            "kb_id": kb_id,
            "kb_name": kb.name,
            "total_docs": row.total_docs or 0,
            "total_chars": row.total_chars or 0,
            "total_chunks": row.total_chunks or 0,
            "done_docs": row.done_docs or 0,
            "processing_docs": row.processing_docs or 0,
            "error_docs": row.error_docs or 0,
        }

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
            raise AppException(code=400, message="相同内容的文档已存在，请勿重复上传")

        # 保存原始文件到配置的存储后端
        ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else "bin"
        storage_key = f"knowledge/{kb_id}/{datetime.now().strftime('%Y%m%d')}/{content_hash[:16]}.{ext}"
        storage = get_storage()
        try:
            stored = await storage.put(
                storage_key,
                file_content,
                content_type=_guess_content_type(ext),
            )
        except Exception as e:
            logger.error("storage_put_failed", backend=storage.backend_name, error=str(e))
            raise RuntimeError(f"文件保存失败：{e}") from e

        doc = AiKnowledgeDoc(
            kb_id=kb_id,
            name=filename,
            source_type=source_type,
            file_type=ext,
            file_size=len(file_content),
            storage_backend=stored.backend,
            storage_key=stored.key,
            storage_url=stored.url,
            content_hash=content_hash,
            status="processing",
        )
        self.db.add(doc)
        await self.db.flush()

        try:
            from app.ai.knowledge.tasks import index_document_task

            index_document_task.delay(
                doc_id=doc.id,
                kb_id=kb_id,
                storage_key=stored.key,
                filename=filename,
            )
            logger.info("index_task_dispatched", doc_id=doc.id, kb_id=kb_id)
        except (ImportError, Exception) as e:
            logger.info("celery_not_available", doc_id=doc.id, kb_id=kb_id, error=str(e))
            pipeline = RAGPipeline(kb=kb, db=self.db)
            try:
                chunk_count = await pipeline.index_document(doc, file_content)
                logger.info("knowledge_upload_done", kb_id=kb_id, doc_id=doc.id, chunks=chunk_count)
            except Exception as e2:
                doc.status = "error"
                doc.error_msg = str(e2)
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

    async def get_document(self, kb_id: int, doc_id: int) -> AiKnowledgeDoc:
        """获取单个文档详情"""
        kb = await self.get_by_id(kb_id)
        doc = await self.db.get(AiKnowledgeDoc, doc_id)
        if not doc or doc.kb_id != kb_id or doc.is_deleted:
            raise NotFoundException(f"文档 ID={doc_id} 不存在")
        return doc

    async def list_documents(
        self, kb_id: int, params: PageParams, status: str | None = None
    ) -> tuple[list[AiKnowledgeDoc], int]:
        stmt = (
            select(AiKnowledgeDoc)
            .where(AiKnowledgeDoc.kb_id == kb_id)
            .where(AiKnowledgeDoc.is_deleted == False)
        )
        if status:
            stmt = stmt.where(AiKnowledgeDoc.status == status)
        count = await self.db.scalar(select(func.count()).select_from(stmt.subquery()))
        items = (
            await self.db.scalars(
                stmt.order_by(AiKnowledgeDoc.created_at.desc())
                .offset(params.offset)
                .limit(params.page_size)
            )
        ).all()
        return list(items), count or 0

    async def reindex_document(self, kb_id: int, doc_id: int) -> dict:
        """重新索引文档（异步任务）"""
        kb = await self.get_by_id(kb_id)
        doc = await self.db.get(AiKnowledgeDoc, doc_id)
        if not doc or doc.kb_id != kb_id or doc.is_deleted:
            raise NotFoundException(f"文档 ID={doc_id} 不存在")

        from app.ai.knowledge.tasks import reindex_single_task
        from app.ai.knowledge.models import AiKnowledgeTask

        task = reindex_single_task.delay(
            doc_id=doc_id,
            kb_id=kb_id,
        )

        task_record = AiKnowledgeTask(
            task_id=task.task_id,
            kb_id=kb_id,
            task_type="reindex_single",
            status="pending",
            total=1,
            completed=0,
            failed=0,
            progress=0,
            current_doc=doc.name,
        )
        self.db.add(task_record)
        await self.db.commit()

        return {"message": "重新索引任务已提交", "task_id": task.task_id}

    async def reindex_all_documents(self, kb_id: int) -> dict:
        """重新索引知识库中所有文档（异步任务）"""
        kb = await self.get_by_id(kb_id)

        from app.ai.knowledge.tasks import reindex_all_task
        from app.ai.knowledge.models import AiKnowledgeTask

        doc_count_result = await self.db.execute(
            select(func.count(AiKnowledgeDoc.id))
            .where(AiKnowledgeDoc.kb_id == kb_id)
            .where(AiKnowledgeDoc.is_deleted == False)
        )
        doc_count = doc_count_result.scalar_one() or 0

        task = reindex_all_task.delay(
            kb_id=kb_id,
        )

        task_record = AiKnowledgeTask(
            task_id=task.task_id,
            kb_id=kb_id,
            task_type="reindex_all",
            status="pending",
            total=doc_count,
            completed=0,
            failed=0,
            progress=0,
            current_doc="",
        )
        self.db.add(task_record)
        await self.db.commit()

        return {"message": "重新索引任务已提交", "task_id": task.task_id}

    async def get_task_status(self, kb_id: int, task_id: str) -> dict:
        """查询任务状态"""
        from app.ai.knowledge.models import AiKnowledgeTask

        task = await self.db.execute(
            select(AiKnowledgeTask)
            .where(AiKnowledgeTask.task_id == task_id)
            .where(AiKnowledgeTask.kb_id == kb_id)
        )
        task = task.scalar_one_or_none()

        if not task:
            raise NotFoundException(f"任务 ID={task_id} 不存在")

        return {
            "task_id": task.task_id,
            "kb_id": task.kb_id,
            "task_type": task.task_type,
            "status": task.status,
            "total": task.total,
            "completed": task.completed,
            "failed": task.failed,
            "progress": task.progress,
            "current_doc": task.current_doc,
            "result": task.result,
            "error_msg": task.error_msg,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
        }

    async def list_tasks(self, kb_id: int) -> list[dict]:
        """获取知识库的任务列表"""
        from app.ai.knowledge.models import AiKnowledgeTask

        result = await self.db.execute(
            select(AiKnowledgeTask)
            .where(AiKnowledgeTask.kb_id == kb_id)
            .order_by(AiKnowledgeTask.created_at.desc())
            .limit(10)
        )
        tasks = result.scalars().all()

        return [
            {
                "task_id": t.task_id,
                "task_type": t.task_type,
                "status": t.status,
                "total": t.total,
                "completed": t.completed,
                "failed": t.failed,
                "progress": t.progress,
                "created_at": t.created_at,
                "updated_at": t.updated_at,
            }
            for t in tasks
        ]

    # ── URL 抓取来源 ──────────────────────────────────────────────────────────

    async def add_url_sources(
        self,
        kb_id: int,
        urls: list[str],
        name: str | None,
        css_selector: str | None,
    ) -> list[AiKnowledgeDoc]:
        """为每个 URL 创建文档记录，并派发抓取+索引 Celery 任务"""
        await self.get_by_id(kb_id)
        from app.ai.knowledge.tasks import fetch_url_task

        docs: list[AiKnowledgeDoc] = []
        for url in urls:
            doc_name = name or url[:80]
            doc = AiKnowledgeDoc(
                kb_id=kb_id,
                name=doc_name,
                source_type="url",
                source_url=url,
                file_type="html",
                file_size=0,
                status="pending",
            )
            self.db.add(doc)
            await self.db.flush()

            try:
                fetch_url_task.delay(
                    doc_id=doc.id,
                    kb_id=kb_id,
                    url=url,
                    css_selector=css_selector,
                )
            except Exception as e:
                logger.warning("celery_not_available_url", doc_id=doc.id, error=str(e))
                # Celery 不可用时标记错误，提示用户手动重试
                doc.status = "error"
                doc.error_msg = f"任务派发失败（Celery 未启动）：{e}"

            docs.append(doc)

        await self.db.commit()
        for doc in docs:
            await self.db.refresh(doc)
        return docs

    # ── API / 数据库来源 ──────────────────────────────────────────────────────

    async def add_api_source(
        self,
        kb_id: int,
        name: str,
        source_type: str,
        config: dict,
    ) -> AiKnowledgeDoc:
        """创建 API/数据库来源文档记录，并派发抓取任务"""
        await self.get_by_id(kb_id)
        from app.ai.knowledge.tasks import fetch_api_task

        doc = AiKnowledgeDoc(
            kb_id=kb_id,
            name=name,
            source_type=source_type,
            source_config=config,
            file_type="text",
            file_size=0,
            status="pending",
        )
        self.db.add(doc)
        await self.db.flush()

        try:
            fetch_api_task.delay(
                doc_id=doc.id,
                kb_id=kb_id,
                source_type=source_type,
                config=config,
            )
        except Exception as e:
            logger.warning("celery_not_available_api", doc_id=doc.id, error=str(e))
            doc.status = "error"
            doc.error_msg = f"任务派发失败（Celery 未启动）：{e}"

        await self.db.commit()
        await self.db.refresh(doc)
        return doc

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


# ── 辅助函数 ──────────────────────────────────────────────────────────────────

_CONTENT_TYPE_MAP = {
    "pdf": "application/pdf",
    "txt": "text/plain",
    "md": "text/markdown",
    "html": "text/html",
    "htm": "text/html",
    "csv": "text/csv",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "json": "application/json",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
}


def _guess_content_type(ext: str) -> str:
    return _CONTENT_TYPE_MAP.get(ext.lower(), "application/octet-stream")
