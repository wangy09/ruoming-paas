"""add integration connection table

Revision ID: 7b2c4d6e8f10
Revises: add_dashboard_template_to_role
Create Date: 2026-07-04 20:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


revision: str = "7b2c4d6e8f10"
down_revision: Union[str, None] = "add_dashboard_template_to_role"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "sys_integration_connection" not in existing_tables:
        op.create_table(
            "sys_integration_connection",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False, comment="创建时间"),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False, comment="更新时间"),
            sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False, comment="软删除标记"),
            sa.Column("tenant_id", sa.BigInteger(), nullable=True, comment="租户ID（NULL=平台级）"),
            sa.Column("provider", sa.String(length=32), nullable=False, comment="平台：feishu/dingtalk/wecom/custom"),
            sa.Column("name", sa.String(length=64), nullable=False, comment="连接名称"),
            sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False, comment="是否启用"),
            sa.Column("is_default", sa.Boolean(), server_default="false", nullable=False, comment="是否默认连接"),
            sa.Column("capabilities", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False, comment="已启用能力"),
            sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment="非敏感配置"),
            sa.Column("encrypted_config", sa.Text(), nullable=True, comment="加密敏感配置 JSON"),
            sa.Column("status", sa.SmallInteger(), server_default="1", nullable=False, comment="状态：1正常 0停用"),
            sa.Column("last_test_status", sa.String(length=16), nullable=True, comment="最近连通性测试状态：success/failed"),
            sa.Column("last_test_message", sa.Text(), nullable=True, comment="最近连通性测试说明"),
            sa.Column("sort", sa.Integer(), server_default="0", nullable=False, comment="排序"),
            sa.Column("created_by", sa.BigInteger(), nullable=True, comment="创建人"),
            sa.Column("updated_by", sa.BigInteger(), nullable=True, comment="更新人"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", "provider", "name", name="uq_integration_tenant_provider_name"),
        )
        op.create_index("ix_sys_integration_connection_tenant_id", "sys_integration_connection", ["tenant_id"])
        op.create_index("ix_sys_integration_connection_provider", "sys_integration_connection", ["provider"])
        op.create_index("ix_sys_integration_connection_enabled", "sys_integration_connection", ["enabled"])
        op.create_index("ix_sys_integration_connection_is_default", "sys_integration_connection", ["is_default"])
        op.create_index("ix_sys_integration_connection_status", "sys_integration_connection", ["status"])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if "sys_integration_connection" in inspector.get_table_names():
        op.drop_index("ix_sys_integration_connection_status", table_name="sys_integration_connection")
        op.drop_index("ix_sys_integration_connection_is_default", table_name="sys_integration_connection")
        op.drop_index("ix_sys_integration_connection_enabled", table_name="sys_integration_connection")
        op.drop_index("ix_sys_integration_connection_provider", table_name="sys_integration_connection")
        op.drop_index("ix_sys_integration_connection_tenant_id", table_name="sys_integration_connection")
        op.drop_table("sys_integration_connection")
