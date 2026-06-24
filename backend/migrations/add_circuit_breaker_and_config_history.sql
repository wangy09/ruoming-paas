-- ============================================================
-- 若茗 PaaS - 数据库迁移脚本
-- 功能：熔断器 + 配置中心变更历史
-- 执行时机：在 Alembic 迁移体系完善前，可直接执行此 SQL
-- ============================================================

-- 1. ai_model_config 新增 is_fallback 字段（熔断备用模型标记）
ALTER TABLE ai_model_config
    ADD COLUMN IF NOT EXISTS is_fallback BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN ai_model_config.is_fallback
    IS '是否为熔断备用模型（主力模型不可用时自动切换）';

-- 2. 配置中心变更历史表
CREATE TABLE IF NOT EXISTS sys_config_history (
    id          BIGSERIAL PRIMARY KEY,
    config_key  VARCHAR(256) NOT NULL,
    scope_type  VARCHAR(20)  NOT NULL,    -- global/tenant/app/user
    scope_id    BIGINT,                   -- tenant_id 或 user_id
    old_value   TEXT,
    new_value   TEXT,
    changed_by  BIGINT,                   -- 操作人 user_id
    changed_at  TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    remark      TEXT
);

CREATE INDEX IF NOT EXISTS idx_config_history_key
    ON sys_config_history (config_key, changed_at DESC);

CREATE INDEX IF NOT EXISTS idx_config_history_scope
    ON sys_config_history (scope_type, scope_id, changed_at DESC);

COMMENT ON TABLE sys_config_history
    IS '配置中心变更历史（合规审计，不可篡改）';
