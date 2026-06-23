-- 若茗 PaaS - 数据库初始化 SQL
-- Author: ruoming
-- PostgreSQL 启动时自动执行

-- 启用 pgvector 扩展（RAG 知识库向量检索）
CREATE EXTENSION IF NOT EXISTS vector;

-- 启用 pg_trgm（全文模糊检索优化）
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 启用 uuid-ossp（UUID 生成）
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ai_knowledge_vector 表由 Alembic 迁移创建（包含 pgvector 向量索引）

-- sys_dept 表和 sys_role.data_scope_depts 字段由 Alembic 迁移创建
-- sys_user.dept_id 字段由 Alembic 迁移创建
