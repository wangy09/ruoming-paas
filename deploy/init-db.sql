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
CREATE TABLE IF NOT EXISTS ai_knowledge_vector (
    id          VARCHAR(128) PRIMARY KEY,
    kb_id       BIGINT NOT NULL,
    doc_id      BIGINT NOT NULL,
    content     TEXT NOT NULL,
    embedding   vector(1536),
    metadata    JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_ai_knowledge_vector_embedding
    ON ai_knowledge_vector USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_ai_knowledge_vector_kb_id
    ON ai_knowledge_vector (kb_id);

-- sys_dept 表和 sys_role.data_scope_depts 字段由 Alembic 迁移创建
-- sys_user.dept_id 字段由 Alembic 迁移创建
