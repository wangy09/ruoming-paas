-- 若茗 PaaS - 数据库初始化 SQL
-- Author: ruoming
-- PostgreSQL 启动时自动执行

-- 启用 pgvector 扩展（RAG 知识库向量检索）
CREATE EXTENSION IF NOT EXISTS vector;

-- 启用 pg_trgm（全文模糊检索优化）
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 启用 uuid-ossp（UUID 生成）
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── AI 知识库向量表（pgvector 专用）────────────────────────────────────────
-- 此表由 pgvector 管理，使用 RAW SQL 操作，不通过 Alembic 迁移。
-- embedding 维度默认 1536（text-embedding-3-small），可按实际模型调整。
CREATE TABLE IF NOT EXISTS ai_knowledge_vector (
    id          VARCHAR(128) PRIMARY KEY,   -- UUID 格式，与 ai_knowledge_chunk.vector_id 对应
    kb_id       BIGINT NOT NULL,            -- 所属知识库 ID
    doc_id      BIGINT NOT NULL,            -- 所属文档 ID
    content     TEXT NOT NULL,             -- 分块原文（检索结果展示用）
    embedding   vector(1536),              -- 向量（维度与 embed 模型一致）
    metadata    JSONB DEFAULT '{}'
);

-- 向量相似度索引（IVFFlat，适合 10万+ 向量；小数据集可用 HNSW）
-- HNSW 索引（PostgreSQL 16+ 推荐，精度更高）
CREATE INDEX IF NOT EXISTS idx_ai_knowledge_vector_embedding
    ON ai_knowledge_vector USING hnsw (embedding vector_cosine_ops);

-- 按知识库 ID 的普通索引（按知识库检索时使用）
CREATE INDEX IF NOT EXISTS idx_ai_knowledge_vector_kb_id
    ON ai_knowledge_vector (kb_id);
