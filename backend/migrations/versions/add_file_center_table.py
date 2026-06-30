"""add file center table

Revision ID: d7e8f9a0b1c2
Revises: c6d7e8f9a0b1
Create Date: 2026-06-30 23:30:00.000000

Author: ruoming
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "d7e8f9a0b1c2"
down_revision: Union[str, None] = "c6d7e8f9a0b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sys_file",
        sa.Column("original_name", sa.String(length=255), nullable=False, comment="原始文件名"),
        sa.Column("file_name", sa.String(length=255), nullable=False, comment="存储文件名"),
        sa.Column("file_ext", sa.String(length=32), nullable=True, comment="文件扩展名"),
        sa.Column("mime_type", sa.String(length=128), nullable=True, comment="MIME 类型"),
        sa.Column("file_size", sa.BigInteger(), nullable=False, comment="文件大小（字节）"),
        sa.Column("file_hash", sa.String(length=64), nullable=False, comment="SHA256 哈希"),
        sa.Column("storage_backend", sa.String(length=32), nullable=False, comment="存储后端：local/minio/oss"),
        sa.Column("storage_key", sa.String(length=512), nullable=False, comment="存储对象 key"),
        sa.Column("storage_url", sa.String(length=1024), nullable=True, comment="存储访问 URL"),
        sa.Column("biz_type", sa.String(length=64), nullable=True, comment="业务类型"),
        sa.Column("biz_id", sa.String(length=64), nullable=True, comment="业务 ID"),
        sa.Column("category", sa.String(length=64), nullable=True, comment="文件分类"),
        sa.Column("remark", sa.String(length=255), nullable=True, comment="备注"),
        sa.Column("uploader_id", sa.BigInteger(), nullable=True, comment="上传人 ID"),
        sa.Column("download_count", sa.Integer(), server_default="0", nullable=False, comment="下载次数"),
        sa.Column("is_public", sa.Boolean(), server_default="false", nullable=False, comment="是否公开"),
        sa.Column("status", sa.SmallInteger(), server_default="1", nullable=False, comment="状态：1正常 2已归档"),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True, comment="归档时间"),
        sa.Column("archived_by", sa.BigInteger(), nullable=True, comment="归档人 ID"),
        sa.Column("archive_reason", sa.Text(), nullable=True, comment="归档原因"),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False, comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False, comment="更新时间"),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False, comment="软删除标记"),
        sa.Column("tenant_id", sa.BigInteger(), nullable=True, comment="租户ID（NULL=平台级）"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
        comment="系统文件表",
    )
    op.create_index(op.f("ix_sys_file_biz_id"), "sys_file", ["biz_id"], unique=False)
    op.create_index(op.f("ix_sys_file_biz_type"), "sys_file", ["biz_type"], unique=False)
    op.create_index(op.f("ix_sys_file_category"), "sys_file", ["category"], unique=False)
    op.create_index(op.f("ix_sys_file_file_ext"), "sys_file", ["file_ext"], unique=False)
    op.create_index(op.f("ix_sys_file_file_hash"), "sys_file", ["file_hash"], unique=False)
    op.create_index(op.f("ix_sys_file_status"), "sys_file", ["status"], unique=False)
    op.create_index(op.f("ix_sys_file_tenant_id"), "sys_file", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_sys_file_uploader_id"), "sys_file", ["uploader_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_sys_file_uploader_id"), table_name="sys_file")
    op.drop_index(op.f("ix_sys_file_tenant_id"), table_name="sys_file")
    op.drop_index(op.f("ix_sys_file_status"), table_name="sys_file")
    op.drop_index(op.f("ix_sys_file_file_hash"), table_name="sys_file")
    op.drop_index(op.f("ix_sys_file_file_ext"), table_name="sys_file")
    op.drop_index(op.f("ix_sys_file_category"), table_name="sys_file")
    op.drop_index(op.f("ix_sys_file_biz_type"), table_name="sys_file")
    op.drop_index(op.f("ix_sys_file_biz_id"), table_name="sys_file")
    op.drop_table("sys_file")
