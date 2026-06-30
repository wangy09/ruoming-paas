"""add config center enhancement fields

Revision ID: e8f9a0b1c2d3
Revises: d7e8f9a0b1c2
Create Date: 2026-07-01 00:30:00.000000

Author: ruoming
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e8f9a0b1c2d3"
down_revision: Union[str, None] = "d7e8f9a0b1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE sys_config ADD COLUMN IF NOT EXISTS category VARCHAR(64)")
    op.execute("ALTER TABLE sys_config ADD COLUMN IF NOT EXISTS config_type VARCHAR(32) NOT NULL DEFAULT 'input'")
    op.execute("ALTER TABLE sys_config ADD COLUMN IF NOT EXISTS default_value TEXT")
    op.execute("ALTER TABLE sys_config ADD COLUMN IF NOT EXISTS options JSONB")
    op.execute("ALTER TABLE sys_config ADD COLUMN IF NOT EXISTS required BOOLEAN NOT NULL DEFAULT false")
    op.execute("ALTER TABLE sys_config ADD COLUMN IF NOT EXISTS regex VARCHAR(255)")
    op.execute("ALTER TABLE sys_config ADD COLUMN IF NOT EXISTS min_value INTEGER")
    op.execute("ALTER TABLE sys_config ADD COLUMN IF NOT EXISTS max_value INTEGER")
    op.execute("ALTER TABLE sys_config ADD COLUMN IF NOT EXISTS sort INTEGER NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE sys_config ADD COLUMN IF NOT EXISTS status SMALLINT NOT NULL DEFAULT 1")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sys_config_category ON sys_config (category)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sys_config_status ON sys_config (status)")
    op.execute("""
        CREATE TABLE IF NOT EXISTS sys_config_history (
            id BIGSERIAL PRIMARY KEY,
            config_key VARCHAR(256) NOT NULL,
            scope_type VARCHAR(20) NOT NULL,
            scope_id BIGINT,
            old_value TEXT,
            new_value TEXT,
            changed_by BIGINT,
            changed_at TIMESTAMPTZ DEFAULT NOW(),
            remark TEXT
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_sys_config_history_config_key ON sys_config_history (config_key)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sys_config_history_changed_at ON sys_config_history (changed_at)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_sys_config_history_changed_at")
    op.execute("DROP INDEX IF EXISTS ix_sys_config_history_config_key")
    op.execute("DROP TABLE IF EXISTS sys_config_history")
    op.execute("DROP INDEX IF EXISTS ix_sys_config_status")
    op.execute("DROP INDEX IF EXISTS ix_sys_config_category")
    op.execute("ALTER TABLE sys_config DROP COLUMN IF EXISTS status")
    op.execute("ALTER TABLE sys_config DROP COLUMN IF EXISTS sort")
    op.execute("ALTER TABLE sys_config DROP COLUMN IF EXISTS max_value")
    op.execute("ALTER TABLE sys_config DROP COLUMN IF EXISTS min_value")
    op.execute("ALTER TABLE sys_config DROP COLUMN IF EXISTS regex")
    op.execute("ALTER TABLE sys_config DROP COLUMN IF EXISTS required")
    op.execute("ALTER TABLE sys_config DROP COLUMN IF EXISTS options")
    op.execute("ALTER TABLE sys_config DROP COLUMN IF EXISTS default_value")
    op.execute("ALTER TABLE sys_config DROP COLUMN IF EXISTS config_type")
    op.execute("ALTER TABLE sys_config DROP COLUMN IF EXISTS category")
