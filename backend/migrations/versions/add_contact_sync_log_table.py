"""add contact sync log table

Revision ID: 9e5f6a7b8c9d
Revises: 9d4e5f6a7b8c
Create Date: 2026-07-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


revision: str = "9e5f6a7b8c9d"
down_revision: Union[str, None] = "9d4e5f6a7b8c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if "sys_contact_sync_log" in inspector.get_table_names():
        return

    op.create_table(
        "sys_contact_sync_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False, comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False, comment="更新时间"),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False, comment="软删除标记"),
        sa.Column("tenant_id", sa.BigInteger(), nullable=True, comment="租户ID（NULL=平台级）"),
        sa.Column("connection_id", sa.BigInteger(), nullable=False, comment="集成连接 ID"),
        sa.Column("provider", sa.String(length=32), nullable=False, comment="平台：dingtalk/wecom/feishu"),
        sa.Column("operation", sa.String(length=16), nullable=False, comment="操作：preview/sync"),
        sa.Column("status", sa.String(length=16), nullable=False, comment="状态：success/partial/failed"),
        sa.Column("operator_id", sa.BigInteger(), nullable=True, comment="操作人 ID"),
        sa.Column("request_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment="同步请求参数"),
        sa.Column("result_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment="同步结果"),
        sa.Column("detail_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment="同步明细摘要"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sys_contact_sync_log_tenant_id", "sys_contact_sync_log", ["tenant_id"])
    op.create_index("ix_sys_contact_sync_log_connection_id", "sys_contact_sync_log", ["connection_id"])
    op.create_index("ix_sys_contact_sync_log_provider", "sys_contact_sync_log", ["provider"])
    op.create_index("ix_sys_contact_sync_log_operation", "sys_contact_sync_log", ["operation"])
    op.create_index("ix_sys_contact_sync_log_status", "sys_contact_sync_log", ["status"])
    op.create_index("ix_sys_contact_sync_log_operator_id", "sys_contact_sync_log", ["operator_id"])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if "sys_contact_sync_log" not in inspector.get_table_names():
        return

    op.drop_index("ix_sys_contact_sync_log_operator_id", table_name="sys_contact_sync_log")
    op.drop_index("ix_sys_contact_sync_log_status", table_name="sys_contact_sync_log")
    op.drop_index("ix_sys_contact_sync_log_operation", table_name="sys_contact_sync_log")
    op.drop_index("ix_sys_contact_sync_log_provider", table_name="sys_contact_sync_log")
    op.drop_index("ix_sys_contact_sync_log_connection_id", table_name="sys_contact_sync_log")
    op.drop_index("ix_sys_contact_sync_log_tenant_id", table_name="sys_contact_sync_log")
    op.drop_table("sys_contact_sync_log")
