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

        task = AiKnowledgeTask(
            task_id=task_id,
            kb_id=kb_id,
            task_type="reindex_single",
            status="running",
            total=1,
            completed=0,
            failed=0,
            progress=0,
            current_doc=doc.name,
        )
        session.add(task)
        session.commit()
        logger.info("reindex_single_task_created", task_id=task_id, kb_id=kb_id, doc_id=doc_id)

        doc.status = "processing"
        doc.error_msg = None
        session.commit()

        session.query(AiKnowledgeChunk).filter(AiKnowledgeChunk.doc_id == doc_id).delete()
        session.execute(
            text("DELETE FROM ai_knowledge_vector WHERE doc_id = :doc_id"),
            {"doc_id": doc_id},
        )
        session.commit()

        storage = get_storage()
        file_content = asyncio.run(storage.get(doc.storage_key))

        text_content = _parse_document(doc.source_type or "text", file_content, doc.name)
        if not text_content.strip():
            logger.warning("knowledge_empty_document", doc_id=doc.id, name=doc.name)
            doc.status = "done"
            doc.chunk_count = 0
            doc.char_count = 0
            session.commit()
            task.status = "completed"
            task.completed = 1
            task.progress = 100
            task.result = {"status": "done", "chunks": 0}
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
            task.progress = 100
            task.result = {"status": "done", "chunks": 0}
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
        task.progress = 100
        task.result = {"status": "done", "chunks": written}
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

        task = AiKnowledgeTask(
            task_id=task_id,
            kb_id=kb_id,
            task_type="reindex_all",
            status="running",
            total=len(docs),
            completed=0,
            failed=0,
            progress=0,
            current_doc="",
        )
        session.add(task)
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

                storage = get_storage()
                file_content = asyncio.run(storage.get(doc.storage_key))

                text_content = _parse_document(doc.source_type or "text", file_content, doc.name)
                if not text_content.strip():
                    logger.warning("knowledge_empty_document", doc_id=doc.id, name=doc.name)
                    doc.status = "done"
                    doc.chunk_count = 0
                    doc.char_count = 0
                    session.commit()
                    success_count += 1
                    continue

                chunks = _split_text(text_content, kb.chunk_size, kb.chunk_overlap)
                if not chunks:
                    doc.status = "done"
                    doc.chunk_count = 0
                    doc.char_count = 0
                    session.commit()
                    success_count += 1
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

            task = session.execute(
                select(AiKnowledgeTask).where(AiKnowledgeTask.task_id == task_id)
            ).scalar_one_or_none()
            if task:
                task.completed = success_count
                task.failed = fail_count
                session.commit()

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