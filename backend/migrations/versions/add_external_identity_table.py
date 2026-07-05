"""add external identity table

Revision ID: 8c3d4e5f6a7b
Revises: 7b2c4d6e8f10
Create Date: 2026-07-04 22:10:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


revision: str = "8c3d4e5f6a7b"
down_revision: Union[str, None] = "7b2c4d6e8f10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if "sys_external_identity" in inspector.get_table_names():
        return

    op.create_table(
        "sys_external_identity",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False, comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False, comment="更新时间"),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False, comment="软删除标记"),
        sa.Column("tenant_id", sa.BigInteger(), nullable=True, comment="租户ID（NULL=平台级）"),
        sa.Column("connection_id", sa.BigInteger(), nullable=False, comment="集成连接 ID"),
        sa.Column("provider", sa.String(length=32), nullable=False, comment="平台：dingtalk/wecom/feishu"),
        sa.Column("identity_type", sa.String(length=16), nullable=False, comment="身份类型：user/dept"),
        sa.Column("external_id", sa.String(length=128), nullable=False, comment="外部平台 ID"),
        sa.Column("local_id", sa.BigInteger(), nullable=False, comment="本地用户或部门 ID"),
        sa.Column("raw_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment="最近一次同步原始数据"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "connection_id",
            "identity_type",
            "external_id",
            name="uq_external_identity_connection_type_external",
        ),
    )
    op.create_index("ix_sys_external_identity_tenant_id", "sys_external_identity", ["tenant_id"])
    op.create_index("ix_sys_external_identity_connection_id", "sys_external_identity", ["connection_id"])
    op.create_index("ix_sys_external_identity_provider", "sys_external_identity", ["provider"])
    op.create_index("ix_sys_external_identity_identity_type", "sys_external_identity", ["identity_type"])
    op.create_index("ix_sys_external_identity_local_id", "sys_external_identity", ["local_id"])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if "sys_external_identity" not in inspector.get_table_names():
        return

    op.drop_index("ix_sys_external_identity_local_id", table_name="sys_external_identity")
    op.drop_index("ix_sys_external_identity_identity_type", table_name="sys_external_identity")
    op.drop_index("ix_sys_external_identity_provider", table_name="sys_external_identity")
    op.drop_index("ix_sys_external_identity_connection_id", table_name="sys_external_identity")
    op.drop_index("ix_sys_external_identity_tenant_id", table_name="sys_external_identity")
    op.drop_table("sys_external_identity")
