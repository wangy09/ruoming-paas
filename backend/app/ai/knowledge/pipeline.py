"""
若茗 PaaS - RAG 处理管道
解析 → 分块 → 向量化 → 存储 → 混合检索（Vector + BM25 + RRF + Rerank）
Author: ruoming
"""
from __future__ import annotations

import asyncio
import hashlib
import uuid
from dataclasses import dataclass, field
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.knowledge.models import AiKnowledgeBase, AiKnowledgeChunk, AiKnowledgeDoc
from app.ai.knowledge.parsers.base import parse_document

logger = structlog.get_logger(__name__)


@dataclass
class TextChunk:
    """文本分块"""
    content: str
    chunk_index: int
    metadata: dict = field(default_factory=dict)


@dataclass
class RetrievedChunk:
    """检索到的分块（含相关性分数）"""
    id: str
    content: str
    doc_id: int
    kb_id: int
    score: float = 0.0
    metadata: dict = field(default_factory=dict)


class RAGPipeline:
    """
    RAG 处理管道。
    - 索引阶段：文档解析 → 文本分块 → 向量化 → 写入 pgvector
    - 检索阶段：向量检索 + BM25 全文检索 → RRF 融合 → Rerank 重排序
    """

    def __init__(
        self,
        kb: AiKnowledgeBase,
        db: AsyncSession,
        embed_model_config_id: int | None = None,
        rerank_model_config_id: int | None = None,
    ) -> None:
        self.kb = kb
        self.db = db
        self.embed_model_config_id = embed_model_config_id or kb.embed_model_id
        self.rerank_model_config_id = rerank_model_config_id or kb.rerank_model_id

    # ── 索引阶段 ───────────────────────────────────────────────────────────────

    async def index_document(self, doc: AiKnowledgeDoc, file_content: bytes) -> int:
        """
        完整索引流程：解析 → 分块 → 向量化 → 写入 DB + pgvector。
        返回成功写入的分块数量。
        """
        try:
            text = parse_document(doc.source_type or "text", file_content, doc.name)
            if not text.strip():
                logger.warning("knowledge_empty_document", doc_id=doc.id, name=doc.name)
                doc.status = "done"
                doc.chunk_count = 0
                doc.char_count = 0
                await self.db.commit()
                return 0

            chunks = self._split_text(text, self.kb.chunk_size, self.kb.chunk_overlap)
            if not chunks:
                doc.status = "done"
                doc.chunk_count = 0
                doc.char_count = 0
                await self.db.commit()
                return 0

            batch_size = 20
            all_embeddings: list[list[float]] = []
            contents = [c.content for c in chunks]
            embed_errors: list[str] = []

            for i in range(0, len(contents), batch_size):
                batch = contents[i: i + batch_size]
                try:
                    embeddings = await self._embed_batch(batch)
                    all_embeddings.extend(embeddings)
                except Exception as e:
                    embed_errors.append(str(e))
                    logger.error("embed_batch_failed", batch_start=i, error=str(e))
                    all_embeddings.extend([[] for _ in batch])

            written = 0
            for i, (chunk, embedding) in enumerate(zip(chunks, all_embeddings)):
                vector_id = str(uuid.uuid4())

                if embedding:
                    await self._upsert_vector(
                        vector_id=vector_id,
                        kb_id=self.kb.id,
                        doc_id=doc.id,
                        content=chunk.content,
                        embedding=embedding,
                        metadata=chunk.metadata,
                    )

                db_chunk = AiKnowledgeChunk(
                    doc_id=doc.id,
                    kb_id=self.kb.id,
                    content=chunk.content,
                    chunk_metadata=chunk.metadata,
                    vector_id=vector_id if embedding else None,
                    chunk_index=i,
                    char_count=len(chunk.content),
                )
                self.db.add(db_chunk)
                written += 1

            doc.status = "done"
            doc.chunk_count = written
            doc.char_count = sum(len(c.content) for c in chunks)
            doc.content_hash = hashlib.sha256(file_content).hexdigest()
            if embed_errors:
                doc.error_msg = "部分向量化失败: " + "; ".join(embed_errors[:3])

            await self.db.commit()
            logger.info("knowledge_index_done", doc_id=doc.id, chunks=written)
            return written

        except Exception as e:
            logger.exception("knowledge_index_failed", doc_id=doc.id, error=str(e))
            doc.status = "error"
            doc.error_msg = str(e)
            try:
                await self.db.commit()
            except Exception as e2:
                logger.error("failed_to_update_doc_status", error=str(e2))
            raise

    async def delete_document_vectors(self, doc_id: int, kb_id: int) -> None:
        """删除文档在向量库（pgvector）和分块表中的所有数据"""
        from sqlalchemy import select, delete

        # 查询该文档的所有 vector_id
        result = await self.db.execute(
            select(AiKnowledgeChunk.vector_id)
            .where(AiKnowledgeChunk.doc_id == doc_id)
            .where(AiKnowledgeChunk.vector_id.isnot(None))
        )
        vector_ids = [row[0] for row in result.fetchall()]

        # 从 pgvector 表删除
        if vector_ids:
            await self.db.execute(
                text("DELETE FROM ai_knowledge_vector WHERE id = ANY(:ids)"),
                {"ids": vector_ids},
            )

        # 删除分块记录
        await self.db.execute(
            delete(AiKnowledgeChunk).where(AiKnowledgeChunk.doc_id == doc_id)
        )
        await self.db.commit()

    # ── 检索阶段 ───────────────────────────────────────────────────────────────

    async def retrieve(self, query: str, top_k: int | None = None) -> list[RetrievedChunk]:
        """
        混合检索入口：
        - vector：仅向量检索
        - bm25：仅全文检索
        - hybrid（默认）：两路并行 + RRF 融合 + 可选 Rerank
        """
        k = top_k or self.kb.top_k

        match self.kb.retrieval_type:
            case "vector":
                return await self._vector_search(query, k)
            case "bm25":
                return await self._bm25_search(query, k)
            case _:  # hybrid
                # 两路并行召回（各取 k*2 以保证候选集）
                vector_results, bm25_results = await asyncio.gather(
                    self._vector_search(query, k * 2),
                    self._bm25_search(query, k * 2),
                )

                # RRF 融合
                merged = self._rrf_merge(vector_results, bm25_results)

                # Rerank（若配置了 Rerank 模型）
                if self.rerank_model_config_id:
                    merged = await self._rerank(query, merged, k)
                else:
                    merged = merged[:k]

                # 过滤低于阈值的结果
                return [c for c in merged if c.score >= self.kb.score_threshold]

    async def retrieve_and_format(self, query: str) -> str:
        """检索并格式化为 LLM 上下文字符串"""
        chunks = await self.retrieve(query)
        if not chunks:
            return ""
        context = "\n\n---\n\n".join(c.content for c in chunks)
        return f"以下是相关参考资料：\n\n{context}"

    # ── 私有：向量检索 ─────────────────────────────────────────────────────────

    async def _vector_search(self, query: str, top_k: int) -> list[RetrievedChunk]:
        """pgvector 余弦相似度检索"""
        try:
            embeddings = await self._embed_batch([query])
            if not embeddings:
                return []
            query_vec = embeddings[0]

            # pgvector 使用 <=> 余弦距离（越小越相似，转为相似度 = 1 - 距离）
            sql = text("""
                SELECT v.id, v.doc_id, v.kb_id, v.content, v.metadata,
                       1 - (v.embedding <=> :query_vec::vector) AS score
                FROM ai_knowledge_vector v
                WHERE v.kb_id = :kb_id
                ORDER BY v.embedding <=> :query_vec::vector
                LIMIT :top_k
            """)
            result = await self.db.execute(
                sql,
                {
                    "query_vec": str(query_vec),  # pgvector 格式 [f1,f2,...]
                    "kb_id": self.kb.id,
                    "top_k": top_k,
                },
            )
            return [
                RetrievedChunk(
                    id=str(row.id),
                    content=row.content,
                    doc_id=row.doc_id,
                    kb_id=row.kb_id,
                    score=float(row.score),
                    metadata=row.metadata or {},
                )
                for row in result.fetchall()
            ]
        except Exception as e:
            logger.warning("vector_search_failed", error=str(e))
            return []

    # ── 私有：BM25 全文检索 ────────────────────────────────────────────────────

    async def _bm25_search(self, query: str, top_k: int) -> list[RetrievedChunk]:
        """PostgreSQL 全文检索（中文需安装 pg_jieba 或使用 simple 配置）"""
        try:
            sql = text("""
                SELECT id, doc_id, kb_id, content, metadata,
                       ts_rank(
                           to_tsvector('simple', content),
                           plainto_tsquery('simple', :query)
                       ) AS score
                FROM ai_knowledge_chunk
                WHERE kb_id = :kb_id
                  AND to_tsvector('simple', content) @@ plainto_tsquery('simple', :query)
                ORDER BY score DESC
                LIMIT :top_k
            """)
            result = await self.db.execute(
                sql,
                {"query": query, "kb_id": self.kb.id, "top_k": top_k},
            )
            return [
                RetrievedChunk(
                    id=str(row.id),
                    content=row.content,
                    doc_id=row.doc_id,
                    kb_id=row.kb_id,
                    score=float(row.score),
                    metadata=row.metadata or {},
                )
                for row in result.fetchall()
            ]
        except Exception as e:
            logger.warning("bm25_search_failed", error=str(e))
            return []

    # ── 私有：RRF 融合 ─────────────────────────────────────────────────────────

    @staticmethod
    def _rrf_merge(
        list1: list[RetrievedChunk],
        list2: list[RetrievedChunk],
        k: int = 60,
    ) -> list[RetrievedChunk]:
        """
        Reciprocal Rank Fusion 融合两路检索结果。
        score = 1/(k + rank)，k 默认 60（学术推荐值）。
        """
        scores: dict[str, float] = {}
        chunks: dict[str, RetrievedChunk] = {}

        for rank, chunk in enumerate(list1):
            scores[chunk.id] = scores.get(chunk.id, 0) + 1 / (k + rank + 1)
            chunks[chunk.id] = chunk

        for rank, chunk in enumerate(list2):
            scores[chunk.id] = scores.get(chunk.id, 0) + 1 / (k + rank + 1)
            chunks[chunk.id] = chunk

        sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)
        merged = [chunks[cid] for cid in sorted_ids]
        # 将 RRF 分数回写（替换原始相关性分数）
        for chunk in merged:
            chunk.score = scores[chunk.id]
        return merged

    # ── 私有：Rerank ──────────────────────────────────────────────────────────

    async def _rerank(
        self, query: str, chunks: list[RetrievedChunk], top_k: int
    ) -> list[RetrievedChunk]:
        """使用 Rerank 模型对候选结果重排序（降低噪音，提升精度）"""
        try:
            from app.ai.llm.service import LLMService
            llm_svc = LLMService()
            provider = await llm_svc.get_provider(self.rerank_model_config_id, self.db)

            # 构建 Rerank 请求（通常 Rerank 模型接受 query + 候选文档列表）
            texts = [c.content for c in chunks]
            # 注意：不同 Rerank 模型 API 格式不同，此处抽象为 embed（余弦重排）
            # 真实 Rerank API（如 Cohere、BGE）可在此定制
            query_emb = (await provider.embed([query], ""))[0]
            doc_embs = await provider.embed(texts, "")

            import numpy as np

            q = np.array(query_emb)
            for chunk, emb in zip(chunks, doc_embs):
                d = np.array(emb)
                score = float(np.dot(q, d) / (np.linalg.norm(q) * np.linalg.norm(d) + 1e-8))
                chunk.score = score

            chunks.sort(key=lambda c: c.score, reverse=True)
            return chunks[:top_k]
        except Exception as e:
            logger.warning("rerank_failed", error=str(e))
            return chunks[:top_k]

    # ── 私有：向量化 ──────────────────────────────────────────────────────────

    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量文本向量化"""
        if not self.embed_model_config_id:
            return [[] for _ in texts]
        try:
            from app.ai.llm.service import LLMService
            llm_svc = LLMService()
            return await llm_svc.embed(texts, self.embed_model_config_id, self.db)
        except Exception as e:
            logger.error("embed_failed", error=str(e))
            return [[] for _ in texts]

    async def _upsert_vector(
        self,
        vector_id: str,
        kb_id: int,
        doc_id: int,
        content: str,
        embedding: list[float],
        metadata: dict,
    ) -> None:
        """向 pgvector 表写入向量（使用 RAW SQL 保证类型正确）"""
        if not embedding:
            return
        vec_str = "[" + ",".join(str(v) for v in embedding) + "]"
        import json
        await self.db.execute(
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
                "kb_id": kb_id,
                "doc_id": doc_id,
                "content": content,
                "embedding": vec_str,
                "metadata": json.dumps(metadata),
            },
        )

    # ── 私有：文本分块 ────────────────────────────────────────────────────────

    @staticmethod
    def _split_text(text: str, chunk_size: int, overlap: int) -> list[TextChunk]:
        """
        递归字符分块（优先按段落/句子边界切割）。
        优先使用 LangChain RecursiveCharacterTextSplitter，降级为手动分块。
        """
        try:
            from langchain.text_splitter import RecursiveCharacterTextSplitter
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=overlap,
                separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""],
            )
            texts = splitter.split_text(text)
        except ImportError:
            # 降级：简单按字符数分块
            texts = []
            start = 0
            while start < len(text):
                end = min(start + chunk_size, len(text))
                texts.append(text[start:end])
                start += chunk_size - overlap
                if start >= len(text):
                    break

        return [
            TextChunk(content=t.strip(), chunk_index=i)
            for i, t in enumerate(texts)
            if t.strip()
        ]
