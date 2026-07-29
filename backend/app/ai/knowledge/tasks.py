"""知识库文档索引异步任务"""
import hashlib
import asyncio
import uuid
from pathlib import Path

import structlog

from app.core.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(bind=True, name="app.ai.knowledge.tasks.index_document")
def index_document_task(
    self,
    doc_id: int,
    kb_id: int,
    storage_key: str,
    filename: str,
):
    from sqlalchemy import create_engine, text, select
    from sqlalchemy.orm import sessionmaker

    from app.ai.knowledge.models import AiKnowledgeBase, AiKnowledgeDoc, AiKnowledgeChunk
    from app.ai.llm.models import AiModelConfig
    from app.config import settings
    from app.core.storage.factory import get_storage
    from app.core.security import decrypt_value

    sync_db_url = settings.DATABASE_URL.replace("+asyncpg", "")
    engine = create_engine(sync_db_url, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        doc = session.get(AiKnowledgeDoc, doc_id)
        if not doc:
            logger.error("doc_not_found", doc_id=doc_id)
            return {"status": "error", "message": "文档不存在"}

        kb = session.get(AiKnowledgeBase, kb_id)
        if not kb:
            doc.status = "error"
            doc.error_msg = "知识库不存在"
            session.commit()
            logger.error("kb_not_found", kb_id=kb_id)
            return {"status": "error", "message": "知识库不存在"}

        doc.status = "processing"
        session.commit()

        storage = get_storage()
        file_content = asyncio.run(storage.get(storage_key))

        text_content = _parse_document(doc.source_type or "text", file_content, filename)
        if not text_content.strip():
            logger.warning("knowledge_empty_document", doc_id=doc.id, name=doc.name)
            doc.status = "done"
            doc.chunk_count = 0
            doc.char_count = 0
            session.commit()
            return {"status": "done", "chunks": 0}

        chunks = _split_text(text_content, kb.chunk_size, kb.chunk_overlap)
        if not chunks:
            doc.status = "done"
            doc.chunk_count = 0
            doc.char_count = 0
            session.commit()
            return {"status": "done", "chunks": 0}

        embeddings = []
        if kb.embed_model_id:
            config = session.execute(
                select(AiModelConfig).where(
                    AiModelConfig.id == kb.embed_model_id,
                    AiModelConfig.is_deleted == False,
                )
            ).scalar_one_or_none()
            if config:
                raw_key = decrypt_value(config.api_key) if config.api_key else ""
                embeddings = asyncio.run(_embed_with_provider(chunks, config, raw_key))
            else:
                logger.warning("embed_model_not_found", model_id=kb.embed_model_id)
                embeddings = [[] for _ in chunks]
        else:
            embeddings = [[] for _ in chunks]

        written = 0
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            vector_id = str(uuid.uuid4())

            if embedding:
                vec_str = "[" + ",".join(str(v) for v in embedding) + "]"
                import json
                session.execute(
                    text("""
                        INSERT INTO ai_knowledge_vector (id, kb_id, doc_id, content, embedding, metadata)
                        VALUES (:vid, :kb_id, :doc_id, :content, :embedding::vector, :metadata::jsonb)
                        ON CONFLICT (id) DO UPDATE
                            SET embedding = EXCLUDED.embedding,
                                content = EXCLUDED.content,
                                metadata = EXCLUDED.metadata
                    """),
                    {
                        "vid": vector_id,
                        "kb_id": kb.id,
                        "doc_id": doc.id,
                        "content": chunk.content,
                        "embedding": vec_str,
                        "metadata": json.dumps(chunk.metadata),
                    },
                )

            db_chunk = AiKnowledgeChunk(
                doc_id=doc.id,
                kb_id=kb.id,
                content=chunk.content,
                chunk_metadata=chunk.metadata,
                vector_id=vector_id if embedding else None,
                chunk_index=i,
                char_count=len(chunk.content),
            )
            session.add(db_chunk)
            written += 1

        doc.status = "done"
        doc.chunk_count = written
        doc.char_count = sum(len(c.content) for c in chunks)
        doc.content_hash = hashlib.sha256(file_content).hexdigest()
        session.commit()

        logger.info(
            "index_document_done",
            doc_id=doc_id,
            kb_id=kb_id,
            chunks=written,
            task_id=self.request.id,
        )
        return {"status": "done", "chunks": written}

    except Exception as e:
        logger.exception("index_document_failed", doc_id=doc_id, error=str(e))
        try:
            doc = session.get(AiKnowledgeDoc, doc_id)
            if doc:
                doc.status = "error"
                doc.error_msg = str(e)
                session.commit()
        except Exception as e2:
            logger.error("failed_to_update_doc_status", error=str(e2))
        return {"status": "error", "message": str(e)}

    finally:
        session.close()
        engine.dispose()


@celery_app.task(name="app.ai.knowledge.tasks.delete_document_vectors")
def delete_document_vectors_task(doc_id: int, kb_id: int):
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    from app.ai.knowledge.models import AiKnowledgeBase, AiKnowledgeChunk
    from app.config import settings

    sync_db_url = settings.DATABASE_URL.replace("+asyncpg", "")
    engine = create_engine(sync_db_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        kb = session.get(AiKnowledgeBase, kb_id)
        if not kb:
            logger.error("kb_not_found", kb_id=kb_id)
            return {"status": "error", "message": "知识库不存在"}

        result = session.query(AiKnowledgeChunk).filter(
            AiKnowledgeChunk.doc_id == doc_id
        ).delete()
        session.execute(
            text("DELETE FROM ai_knowledge_vector WHERE doc_id = :doc_id"),
            {"doc_id": doc_id},
        )
        session.commit()
        logger.info("delete_vectors_done", doc_id=doc_id, deleted=result)
        return {"status": "done"}

    except Exception as e:
        logger.exception("delete_vectors_failed", doc_id=doc_id, error=str(e))
        return {"status": "error", "message": str(e)}

    finally:
        session.close()
        engine.dispose()


@celery_app.task(bind=True, name="app.ai.knowledge.tasks.reindex_single_task")
def reindex_single_task(
    self,
    doc_id: int,
    kb_id: int,
):
    from sqlalchemy import create_engine, text, select
    from sqlalchemy.orm import sessionmaker

    from app.ai.knowledge.models import AiKnowledgeBase, AiKnowledgeDoc, AiKnowledgeChunk, AiKnowledgeTask
    from app.ai.llm.models import AiModelConfig
    from app.config import settings
    from app.core.storage.factory import get_storage
    from app.core.security import decrypt_value

    sync_db_url = settings.DATABASE_URL.replace("+asyncpg", "")
    engine = create_engine(sync_db_url, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)
    session = Session()

    task_id = self.request.id

    try:
        doc = session.get(AiKnowledgeDoc, doc_id)
        if not doc:
            logger.error("doc_not_found", doc_id=doc_id)
            return {"status": "error", "message": "文档不存在"}

        kb = session.get(AiKnowledgeBase, kb_id)
        if not kb:
            logger.error("kb_not_found", kb_id=kb_id)
            return {"status": "error", "message": "知识库不存在"}

        task = session.execute(
            select(AiKnowledgeTask).where(AiKnowledgeTask.task_id == task_id)
        ).scalar_one_or_none()

        if task:
            task.status = "running"
            task.current_doc = doc.name
            session.commit()
        logger.info("reindex_single_task_started", task_id=task_id, kb_id=kb_id, doc_id=doc_id)

        doc.status = "processing"
        doc.error_msg = None
        session.commit()

        session.query(AiKnowledgeChunk).filter(AiKnowledgeChunk.doc_id == doc_id).delete()
        session.execute(
            text("DELETE FROM ai_knowledge_vector WHERE doc_id = :doc_id"),
            {"doc_id": doc_id},
        )
        session.commit()

        # ── 非 file 来源：重新派发对应的 fetch 任务 ──────────────────────────
        source_type = doc.source_type or "file"
        if source_type == "url":
            if not doc.source_url:
                raise ValueError("URL 来源文档缺少 source_url，无法重建索引")
            doc.status = "pending"
            session.commit()
            fetch_url_task.apply_async(
                kwargs={"doc_id": doc_id, "kb_id": kb_id, "url": doc.source_url, "css_selector": None},
                queue="knowledge",
            )
            logger.info("reindex_single_dispatched_url", doc_id=doc_id, url=doc.source_url)
            if task:
                task.status = "completed"
                task.completed = 1
                task.failed = 0
                task.progress = 100
                task.result = {"status": "done", "success": 1, "failed": 0, "message": "已重新派发 URL 抓取任务"}
                session.commit()
            return {"status": "done", "success": 1, "failed": 0, "message": "已重新派发 URL 抓取任务"}

        if source_type in ("api", "database"):
            if not doc.source_config:
                raise ValueError(f"{source_type} 来源文档缺少 source_config，无法重建索引")
            doc.status = "pending"
            session.commit()
            fetch_api_task.apply_async(
                kwargs={"doc_id": doc_id, "kb_id": kb_id, "source_type": source_type, "config": doc.source_config},
                queue="knowledge",
            )
            logger.info("reindex_single_dispatched_api", doc_id=doc_id, source_type=source_type)
            if task:
                task.status = "completed"
                task.completed = 1
                task.failed = 0
                task.progress = 100
                task.result = {"status": "done", "success": 1, "failed": 0, "message": f"已重新派发 {source_type} 抓取任务"}
                session.commit()
            return {"status": "done", "success": 1, "failed": 0, "message": f"已重新派发 {source_type} 抓取任务"}

        # ── file 来源：读 storage_key ─────────────────────────────────────────
        storage = get_storage()
        file_content = asyncio.run(storage.get(doc.storage_key))

        text_content = _parse_document(source_type, file_content, doc.name)
        if not text_content.strip():
            logger.warning("knowledge_empty_document", doc_id=doc.id, name=doc.name)
            doc.status = "done"
            doc.chunk_count = 0
            doc.char_count = 0
            session.commit()
            task.status = "completed"
            task.completed = 1
            task.failed = 0
            task.progress = 100
            task.result = {"status": "done", "chunks": 0, "success": 1, "failed": 0}
            session.commit()
            logger.info("reindex_single_done_empty", task_id=task_id, kb_id=kb_id, doc_id=doc_id)
            return {"status": "done", "chunks": 0}

        chunks = _split_text(text_content, kb.chunk_size, kb.chunk_overlap)
        if not chunks:
            doc.status = "done"
            doc.chunk_count = 0
            doc.char_count = 0
            session.commit()
            task.status = "completed"
            task.completed = 1
            task.failed = 0
            task.progress = 100
            task.result = {"status": "done", "chunks": 0, "success": 1, "failed": 0}
            session.commit()
            logger.info("reindex_single_done_no_chunks", task_id=task_id, kb_id=kb_id, doc_id=doc_id)
            return {"status": "done", "chunks": 0}

        embeddings = []
        if kb.embed_model_id:
            config = session.execute(
                select(AiModelConfig).where(
                    AiModelConfig.id == kb.embed_model_id,
                    AiModelConfig.is_deleted == False,
                )
            ).scalar_one_or_none()
            if config:
                raw_key = decrypt_value(config.api_key) if config.api_key else ""
                embeddings = asyncio.run(_embed_with_provider(chunks, config, raw_key))
            else:
                logger.warning("embed_model_not_found", model_id=kb.embed_model_id)
                embeddings = [[] for _ in chunks]
        else:
            embeddings = [[] for _ in chunks]

        written = 0
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            vector_id = str(uuid.uuid4())

            if embedding:
                vec_str = "[" + ",".join(str(v) for v in embedding) + "]"
                import json
                session.execute(
                    text("""
                        INSERT INTO ai_knowledge_vector (id, kb_id, doc_id, content, embedding, metadata)
                        VALUES (:vid, :kb_id, :doc_id, :content, :embedding::vector, :metadata::jsonb)
                        ON CONFLICT (id) DO UPDATE
                            SET embedding = EXCLUDED.embedding,
                                content = EXCLUDED.content,
                                metadata = EXCLUDED.metadata
                    """),
                    {
                        "vid": vector_id,
                        "kb_id": kb.id,
                        "doc_id": doc.id,
                        "content": chunk.content,
                        "embedding": vec_str,
                        "metadata": json.dumps(chunk.metadata),
                    },
                )

            db_chunk = AiKnowledgeChunk(
                doc_id=doc.id,
                kb_id=kb.id,
                content=chunk.content,
                chunk_metadata=chunk.metadata,
                vector_id=vector_id if embedding else None,
                chunk_index=i,
                char_count=len(chunk.content),
            )
            session.add(db_chunk)
            written += 1

        doc.status = "done"
        doc.chunk_count = written
        doc.char_count = sum(len(c.content) for c in chunks)
        doc.content_hash = hashlib.sha256(file_content).hexdigest()
        session.commit()

        task.status = "completed"
        task.completed = 1
        task.failed = 0
        task.progress = 100
        task.result = {"status": "done", "chunks": written, "success": 1, "failed": 0}
        session.commit()

        logger.info(
            "reindex_single_done",
            doc_id=doc_id,
            kb_id=kb_id,
            chunks=written,
            task_id=task_id,
        )
        return {"status": "done", "chunks": written}

    except Exception as e:
        logger.exception("reindex_single_failed", doc_id=doc_id, error=str(e))
        try:
            doc = session.get(AiKnowledgeDoc, doc_id)
            if doc:
                doc.status = "error"
                doc.error_msg = str(e)
                session.commit()
        except Exception as e2:
            logger.error("failed_to_update_doc_status", error=str(e2))
        try:
            task = session.execute(
                select(AiKnowledgeTask).where(AiKnowledgeTask.task_id == task_id)
            ).scalar_one_or_none()
            if task:
                task.status = "failed"
                task.failed = 1
                task.error_msg = str(e)
                session.commit()
                logger.info("reindex_single_failed_task_updated", task_id=task_id, kb_id=kb_id, doc_id=doc_id)
        except Exception as e3:
            logger.error("failed_to_update_task_status", error=str(e3))
        return {"status": "error", "message": str(e)}

    finally:
        session.close()
        engine.dispose()


@celery_app.task(bind=True, name="app.ai.knowledge.tasks.reindex_all_task")
def reindex_all_task(
    self,
    kb_id: int,
):
    from sqlalchemy import create_engine, text, select
    from sqlalchemy.orm import sessionmaker

    from app.ai.knowledge.models import AiKnowledgeBase, AiKnowledgeDoc, AiKnowledgeChunk, AiKnowledgeTask
    from app.ai.llm.models import AiModelConfig
    from app.config import settings
    from app.core.storage.factory import get_storage
    from app.core.security import decrypt_value

    sync_db_url = settings.DATABASE_URL.replace("+asyncpg", "")
    engine = create_engine(sync_db_url, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)
    session = Session()

    task_id = self.request.id
    logger.info("reindex_all_task_started", kb_id=kb_id, task_id=task_id)
    success_count = 0
    fail_count = 0
    failed_docs = []

    try:
        kb = session.get(AiKnowledgeBase, kb_id)
        if not kb:
            logger.error("kb_not_found", kb_id=kb_id)
            return {"status": "error", "message": "知识库不存在"}

        docs_result = session.execute(
            select(AiKnowledgeDoc)
            .where(AiKnowledgeDoc.kb_id == kb_id)
            .where(AiKnowledgeDoc.is_deleted == False)
        )
        docs = docs_result.scalars().all()
        logger.info("docs_found", kb_id=kb_id, doc_count=len(docs))

        task = session.execute(
            select(AiKnowledgeTask).where(AiKnowledgeTask.task_id == task_id)
        ).scalar_one_or_none()

        if task:
            task.status = "running"
            task.total = len(docs)
            session.commit()

        for i, doc in enumerate(docs):
            try:
                task = session.execute(
                    select(AiKnowledgeTask).where(AiKnowledgeTask.task_id == task_id)
                ).scalar_one_or_none()
                if task:
                    task.current_doc = doc.name
                    task.progress = int(((i + 1) / len(docs)) * 100)
                    logger.info("progress_update", kb_id=kb_id, task_id=task_id, progress=task.progress, current_doc=doc.name)
                    session.commit()

                doc.status = "processing"
                doc.error_msg = None
                session.commit()

                session.query(AiKnowledgeChunk).filter(AiKnowledgeChunk.doc_id == doc.id).delete()
                session.execute(
                    text("DELETE FROM ai_knowledge_vector WHERE doc_id = :doc_id"),
                    {"doc_id": doc.id},
                )
                session.commit()

                # 非 file 来源：重新派发对应 fetch 任务，不读 storage_key
                _source_type = doc.source_type or "file"
                if _source_type == "url":
                    if doc.source_url:
                        doc.status = "pending"
                        session.commit()
                        fetch_url_task.apply_async(
                            kwargs={"doc_id": doc.id, "kb_id": kb_id, "url": doc.source_url, "css_selector": None},
                            queue="knowledge",
                        )
                        logger.info("reindex_all_dispatched_url", doc_id=doc.id, url=doc.source_url)
                        success_count += 1
                    else:
                        doc.status = "error"
                        doc.error_msg = "URL 来源文档缺少 source_url"
                        session.commit()
                        fail_count += 1
                        failed_docs.append({"doc_id": doc.id, "name": doc.name, "error": "缺少 source_url"})
                    _update_task_progress(session, task_id, success_count, fail_count)
                    continue

                if _source_type in ("api", "database"):
                    if doc.source_config:
                        doc.status = "pending"
                        session.commit()
                        fetch_api_task.apply_async(
                            kwargs={"doc_id": doc.id, "kb_id": kb_id, "source_type": _source_type, "config": doc.source_config},
                            queue="knowledge",
                        )
                        logger.info("reindex_all_dispatched_api", doc_id=doc.id, source_type=_source_type)
                        success_count += 1
                    else:
                        doc.status = "error"
                        doc.error_msg = f"{_source_type} 来源文档缺少 source_config"
                        session.commit()
                        fail_count += 1
                        failed_docs.append({"doc_id": doc.id, "name": doc.name, "error": "缺少 source_config"})
                    _update_task_progress(session, task_id, success_count, fail_count)
                    continue

                storage = get_storage()
                file_content = asyncio.run(storage.get(doc.storage_key))

                text_content = _parse_document(_source_type, file_content, doc.name)
                if not text_content.strip():
                    logger.warning("knowledge_empty_document", doc_id=doc.id, name=doc.name)
                    doc.status = "done"
                    doc.chunk_count = 0
                    doc.char_count = 0
                    session.commit()
                    success_count += 1
                    _update_task_progress(session, task_id, success_count, fail_count)
                    continue

                chunks = _split_text(text_content, kb.chunk_size, kb.chunk_overlap)
                if not chunks:
                    doc.status = "done"
                    doc.chunk_count = 0
                    doc.char_count = 0
                    session.commit()
                    success_count += 1
                    _update_task_progress(session, task_id, success_count, fail_count)
                    continue

                embeddings = []
                if kb.embed_model_id:
                    config = session.execute(
                        select(AiModelConfig).where(
                            AiModelConfig.id == kb.embed_model_id,
                            AiModelConfig.is_deleted == False,
                        )
                    ).scalar_one_or_none()
                    if config:
                        raw_key = decrypt_value(config.api_key) if config.api_key else ""
                        embeddings = asyncio.run(_embed_with_provider(chunks, config, raw_key))
                    else:
                        logger.warning("embed_model_not_found", model_id=kb.embed_model_id)
                        embeddings = [[] for _ in chunks]
                else:
                    embeddings = [[] for _ in chunks]

                written = 0
                for j, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                    vector_id = str(uuid.uuid4())

                    if embedding:
                        vec_str = "[" + ",".join(str(v) for v in embedding) + "]"
                        import json
                        session.execute(
                            text("""
                                INSERT INTO ai_knowledge_vector (id, kb_id, doc_id, content, embedding, metadata)
                                VALUES (:vid, :kb_id, :doc_id, :content, :embedding::vector, :metadata::jsonb)
                                ON CONFLICT (id) DO UPDATE
                                    SET embedding = EXCLUDED.embedding,
                                        content = EXCLUDED.content,
                                        metadata = EXCLUDED.metadata
                            """),
                            {
                                "vid": vector_id,
                                "kb_id": kb.id,
                                "doc_id": doc.id,
                                "content": chunk.content,
                                "embedding": vec_str,
                                "metadata": json.dumps(chunk.metadata),
                            },
                        )

                    db_chunk = AiKnowledgeChunk(
                        doc_id=doc.id,
                        kb_id=kb.id,
                        content=chunk.content,
                        chunk_metadata=chunk.metadata,
                        vector_id=vector_id if embedding else None,
                        chunk_index=j,
                        char_count=len(chunk.content),
                    )
                    session.add(db_chunk)
                    written += 1

                doc.status = "done"
                doc.chunk_count = written
                doc.char_count = sum(len(c.content) for c in chunks)
                doc.content_hash = hashlib.sha256(file_content).hexdigest()
                session.commit()

                success_count += 1

            except Exception as e:
                logger.exception("reindex_doc_failed", doc_id=doc.id, error=str(e))
                try:
                    doc_obj = session.get(AiKnowledgeDoc, doc.id)
                    if doc_obj:
                        doc_obj.status = "error"
                        doc_obj.error_msg = str(e)
                        session.commit()
                except Exception as e2:
                    logger.error("failed_to_update_doc_status", error=str(e2))
                fail_count += 1
                failed_docs.append({"doc_id": doc.id, "name": doc.name, "error": str(e)})

            _update_task_progress(session, task_id, success_count, fail_count)

        task = session.execute(
            select(AiKnowledgeTask).where(AiKnowledgeTask.task_id == task_id)
        ).scalar_one_or_none()
        if task:
            task.status = "completed"
            task.progress = 100
            task.current_doc = ""
            task.result = {
                "total": len(docs),
                "success": success_count,
                "failed": fail_count,
                "failed_docs": failed_docs,
            }
            session.commit()
            logger.info("reindex_all_done", kb_id=kb_id, total=len(docs), success=success_count, failed=fail_count, task_id=task_id)

        return {
            "status": "done",
            "total": len(docs),
            "success": success_count,
            "failed": fail_count,
            "failed_docs": failed_docs,
        }

    except Exception as e:
        logger.exception("reindex_all_failed", kb_id=kb_id, error=str(e))
        try:
            task = session.execute(
                select(AiKnowledgeTask).where(AiKnowledgeTask.task_id == task_id)
            ).scalar_one_or_none()
            if task:
                task.status = "failed"
                task.error_msg = str(e)
                session.commit()
        except Exception as e2:
            logger.error("failed_to_update_task_status", error=str(e2))
        return {"status": "error", "message": str(e)}

    finally:
        session.close()
        engine.dispose()


def _parse_document(source_type: str, file_content: bytes, filename: str) -> str:
    from app.ai.knowledge.parsers.base import parse_document
    return parse_document(source_type, file_content, filename)


def _split_text(text: str, chunk_size: int, overlap: int) -> list:
    try:
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=overlap,
            separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""],
        )
        texts = splitter.split_text(text)
    except ImportError:
        texts = []
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            texts.append(text[start:end])
            start += chunk_size - overlap
            if start >= len(text):
                break

    class TextChunk:
        def __init__(self, content, chunk_index, metadata=None):
            self.content = content
            self.chunk_index = chunk_index
            self.metadata = metadata or {}

    return [
        TextChunk(content=t.strip(), chunk_index=i)
        for i, t in enumerate(texts)
        if t.strip()
    ]


async def _embed_with_provider(chunks, config, api_key):
    from app.ai.llm.providers.openai_compat import OpenAICompatProvider
    from app.ai.llm.providers.zhuilu import ZhuiluProvider
    from app.config import settings

    match config.provider:
        case "zhuilu":
            provider = ZhuiluProvider(
                api_key=api_key,
                base_url=config.base_url or settings.ZHUILU_BASE_URL,
            )
        case "openai":
            provider = OpenAICompatProvider(
                api_key=api_key,
                base_url=config.base_url or settings.OPENAI_BASE_URL,
                provider_name="openai",
            )
        case "ollama":
            provider = OpenAICompatProvider(
                api_key="",
                base_url=config.base_url or settings.OLLAMA_BASE_URL,
                provider_name="ollama",
            )
        case "azure":
            provider = OpenAICompatProvider(
                api_key=api_key,
                base_url=config.base_url or "",
                provider_name="azure",
            )
        case _:
            logger.error("unsupported_provider", provider=config.provider)
            return [[] for _ in chunks]

    contents = [c.content for c in chunks]
    return await provider.embed(contents, config.model_id)


# ── URL 抓取任务 ──────────────────────────────────────────────────────────────

@celery_app.task(bind=True, name="app.ai.knowledge.tasks.fetch_url_task")
def fetch_url_task(self, doc_id: int, kb_id: int, url: str, css_selector: str | None = None):
    """抓取 URL 页面内容并写入向量索引"""
    import asyncio
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.ai.knowledge.models import AiKnowledgeBase, AiKnowledgeDoc
    from app.config import settings

    sync_db_url = settings.DATABASE_URL.replace("+asyncpg", "")
    engine = create_engine(sync_db_url, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        doc = session.get(AiKnowledgeDoc, doc_id)
        kb = session.get(AiKnowledgeBase, kb_id)
        if not doc or not kb:
            return {"status": "error", "message": "记录不存在"}

        doc.status = "processing"
        session.commit()

        # 抓取网页
        html_content = asyncio.run(_fetch_url(url))

        # 用 HTML 解析器提取正文
        extracted_text = _extract_html_text(html_content, css_selector)
        file_content = extracted_text.encode("utf-8")
        if not extracted_text.strip():
            # 区分：纯空页面 vs SPA（页面有内容但全是 JS 渲染）
            raw_len = len(html_content)
            if raw_len < 500:
                err_msg = f"页面内容为空（响应长度 {raw_len} 字节）"
            else:
                err_msg = (
                    f"无法提取页面正文（响应 {raw_len} 字节但文本为空）。"
                    "该页面可能是 JavaScript 渲染的 SPA，暂不支持直接抓取。"
                    "建议改用 API 来源，或提供页面的静态版本 URL。"
                )
            doc.status = "error"
            doc.error_msg = err_msg
            session.commit()
            return {"status": "error", "message": err_msg}

        # 复用现有索引流程
        _run_index_pipeline(session, doc, kb, file_content, url)
        return {"status": "done"}

    except Exception as e:
        logger.exception("fetch_url_task_failed", doc_id=doc_id, url=url, error=str(e))
        try:
            doc = session.get(AiKnowledgeDoc, doc_id)
            if doc:
                doc.status = "error"
                doc.error_msg = str(e)[:500]
                session.commit()
        except Exception as db_err:
            logger.warning("fetch_url_task_db_update_failed", doc_id=doc_id, error=str(db_err))
        return {"status": "error", "message": str(e)}
    finally:
        session.close()
        engine.dispose()


# ── API / 数据库来源任务 ────────────────────────────────────────────────────────

@celery_app.task(bind=True, name="app.ai.knowledge.tasks.fetch_api_task")
def fetch_api_task(
    self,
    doc_id: int,
    kb_id: int,
    source_type: str,
    config: dict,
):
    """从外部 API 或数据库获取内容并写入向量索引"""
    import asyncio
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.ai.knowledge.models import AiKnowledgeBase, AiKnowledgeDoc
    from app.config import settings

    sync_db_url = settings.DATABASE_URL.replace("+asyncpg", "")
    engine = create_engine(sync_db_url, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        doc = session.get(AiKnowledgeDoc, doc_id)
        kb = session.get(AiKnowledgeBase, kb_id)
        if not doc or not kb:
            return {"status": "error", "message": "记录不存在"}

        doc.status = "processing"
        session.commit()

        if source_type == "api":
            text_content = asyncio.run(_fetch_api_content(config))
        elif source_type == "database":
            text_content = _fetch_db_content(config)
        else:
            raise ValueError(f"不支持的来源类型: {source_type}")

        if not text_content.strip():
            doc.status = "error"
            doc.error_msg = "获取到的内容为空"
            session.commit()
            return {"status": "error", "message": "内容为空"}

        file_content = text_content.encode("utf-8")
        _run_index_pipeline(session, doc, kb, file_content, doc.name)
        return {"status": "done"}

    except Exception as e:
        logger.exception("fetch_api_task_failed", doc_id=doc_id, error=str(e))
        try:
            doc = session.get(AiKnowledgeDoc, doc_id)
            if doc:
                doc.status = "error"
                doc.error_msg = str(e)[:500]
                session.commit()
        except Exception as db_err:
            logger.warning("fetch_api_task_db_update_failed", doc_id=doc_id, error=str(db_err))
        return {"status": "error", "message": str(e)}
    finally:
        session.close()
        engine.dispose()


# ── 任务辅助函数 ──────────────────────────────────────────────────────────────

async def _fetch_url(url: str, timeout: int = 30, retries: int = 3) -> str:
    """异步抓取 URL，返回 HTML 字符串（带重试）"""
    import httpx
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                encoding = resp.encoding or "utf-8"
                return resp.content.decode(encoding, errors="replace")
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            last_exc = e
            if attempt < retries - 1:
                await asyncio.sleep(2 ** attempt)  # 指数退避：1s, 2s
            continue
    raise last_exc or RuntimeError(f"无法访问 URL: {url}")


def _extract_html_text(html: str, css_selector: str | None = None) -> str:
    """从 HTML 提取正文，可选 CSS 选择器"""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        # 移除 script / style / nav / footer
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        if css_selector:
            nodes = soup.select(css_selector)
            return "\n\n".join(n.get_text(separator="\n", strip=True) for n in nodes)

        # 优先提取 main / article，降级到 body
        main = soup.find("main") or soup.find("article") or soup.find("body")
        if main:
            return main.get_text(separator="\n", strip=True)
        return soup.get_text(separator="\n", strip=True)
    except ImportError:
        import re
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        return re.sub(r"\s+", " ", text).strip()


async def _fetch_api_content(config: dict) -> str:
    """调用外部 HTTP API 获取内容"""
    import httpx
    import json

    url = config.get("url", "")
    method = config.get("method", "GET").upper()
    headers = config.get("headers", {})
    body = config.get("body")
    json_path = config.get("json_path")

    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        kwargs: dict = {"headers": headers}
        if body:
            kwargs["content"] = body
            if "Content-Type" not in headers:
                kwargs["headers"] = {**headers, "Content-Type": "application/json"}
        resp = await client.request(method, url, **kwargs)
        resp.raise_for_status()

    # 尝试 JSON 解析 + JSONPath 提取
    if json_path:
        try:
            data = resp.json()
            # 简单 JSONPath 解析（支持 $.field.subfield 形式）
            keys = json_path.lstrip("$").lstrip(".").split(".")
            val = data
            for k in keys:
                if isinstance(val, dict):
                    val = val.get(k, "")
                elif isinstance(val, list):
                    val = "\n".join(str(item.get(k, "")) if isinstance(item, dict) else str(item) for item in val)
                    break
            if isinstance(val, list):
                return "\n".join(str(v) for v in val)
            return str(val)
        except Exception:
            pass

    # 尝试 JSON → 文本
    try:
        data = resp.json()
        return json.dumps(data, ensure_ascii=False, indent=2)
    except Exception:
        return resp.text


def _fetch_db_content(config: dict) -> str:
    """同步查询数据库并将结果拼接为文本"""
    import sqlalchemy as sa

    db_url = config.get("db_url", "")
    sql = config.get("sql", "")
    if not db_url or not sql:
        raise ValueError("db_url 和 sql 不能为空")

    engine = sa.create_engine(db_url, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            result = conn.execute(sa.text(sql))
            rows = result.fetchall()
            cols = list(result.keys())
            lines = ["\t".join(str(v) for v in row) for row in rows]
            header = "\t".join(cols)
            return header + "\n" + "\n".join(lines)
    finally:
        engine.dispose()


def _update_task_progress(session, task_id: str, success_count: int, fail_count: int):
    """更新 AiKnowledgeTask 的 completed/failed 计数"""
    from sqlalchemy import select
    from app.ai.knowledge.models import AiKnowledgeTask
    try:
        task = session.execute(
            select(AiKnowledgeTask).where(AiKnowledgeTask.task_id == task_id)
        ).scalar_one_or_none()
        if task:
            task.completed = success_count
            task.failed = fail_count
            session.commit()
    except Exception as e:
        logger.error("update_task_progress_failed", task_id=task_id, error=str(e))


def _run_index_pipeline(session, doc, kb, file_content: bytes, source_hint: str):
    """复用 index_document_task 的索引核心逻辑"""
    import asyncio
    import uuid
    import hashlib
    from sqlalchemy import select, text
    from sqlalchemy.orm import Session as SASession

    from app.ai.knowledge.models import AiKnowledgeChunk
    from app.ai.llm.models import AiModelConfig
    from app.core.security import decrypt_value

    chunks = _split_text(
        _parse_document(doc.source_type or "text", file_content, source_hint),
        kb.chunk_size,
        kb.chunk_overlap,
    )

    embeddings = []
    if kb.embed_model_id:
        config = session.execute(
            select(AiModelConfig).where(
                AiModelConfig.id == kb.embed_model_id,
                AiModelConfig.is_deleted == False,  # noqa: E712
            )
        ).scalar_one_or_none()
        if config:
            raw_key = decrypt_value(config.api_key) if config.api_key else ""
            embeddings = asyncio.run(_embed_with_provider(chunks, config, raw_key))
        else:
            embeddings = [[] for _ in chunks]
    else:
        embeddings = [[] for _ in chunks]

    import json as _json
    written = 0
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        vector_id = str(uuid.uuid4())
        if embedding:
            vec_str = "[" + ",".join(str(v) for v in embedding) + "]"
            session.execute(
                text("""
                    INSERT INTO ai_knowledge_vector (id, kb_id, doc_id, content, embedding, metadata)
                    VALUES (:vid, :kb_id, :doc_id, :content, :embedding::vector, :metadata::jsonb)
                    ON CONFLICT (id) DO UPDATE
                        SET embedding = EXCLUDED.embedding,
                            content = EXCLUDED.content,
                            metadata = EXCLUDED.metadata
                """),
                {
                    "vid": vector_id,
                    "kb_id": kb.id,
                    "doc_id": doc.id,
                    "content": chunk.content,
                    "embedding": vec_str,
                    "metadata": _json.dumps(chunk.metadata),
                },
            )
        db_chunk = AiKnowledgeChunk(
            doc_id=doc.id,
            kb_id=kb.id,
            content=chunk.content,
            chunk_metadata=chunk.metadata,
            vector_id=vector_id if embedding else None,
            chunk_index=i,
            char_count=len(chunk.content),
        )
        session.add(db_chunk)
        written += 1

    doc.status = "done"
    doc.chunk_count = written
    doc.char_count = sum(len(c.content) for c in chunks)
    doc.content_hash = hashlib.sha256(file_content).hexdigest()
    session.commit()
    logger.info("run_index_pipeline_done", doc_id=doc.id, kb_id=kb.id, chunks=written)