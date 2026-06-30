"""add message center tables

Revision ID: c6d7e8f9a0b1
Revises: b1c2d3e4f5a6
Create Date: 2026-06-30 22:30:00.000000

Author: ruoming
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c6d7e8f9a0b1'
down_revision: Union[str, None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'sys_notice',
        sa.Column('title', sa.String(length=128), nullable=False, comment='公告标题'),
        sa.Column('content', sa.Text(), nullable=False, comment='公告内容'),
        sa.Column('notice_type', sa.String(length=32), server_default='notice', nullable=False, comment='公告类型：notice=公告'),
        sa.Column('target_type', sa.String(length=16), nullable=False, comment='投放范围：all=全平台/dept=部门/user=指定用户'),
        sa.Column('target_dept_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='目标部门 ID 列表'),
        sa.Column('target_user_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='目标用户 ID 列表'),
        sa.Column('status', sa.SmallInteger(), server_default='0', nullable=False, comment='状态：0草稿 1已发布'),
        sa.Column('publisher_id', sa.BigInteger(), nullable=True, comment='发布人 ID'),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True, comment='发布时间'),
        sa.Column('receiver_count', sa.Integer(), server_default='0', nullable=False, comment='接收人数'),
        sa.Column('remark', sa.String(length=255), nullable=True, comment='备注'),
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='主键'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='更新时间'),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False, comment='软删除标记'),
        sa.Column('tenant_id', sa.BigInteger(), nullable=True, comment='租户ID（NULL=平台级）'),
        sa.PrimaryKeyConstraint('id'),
        comment='平台公告表',
    )
    op.create_index(op.f('ix_sys_notice_publisher_id'), 'sys_notice', ['publisher_id'], unique=False)
    op.create_index(op.f('ix_sys_notice_tenant_id'), 'sys_notice', ['tenant_id'], unique=False)

    op.create_table(
        'sys_user_message',
        sa.Column('notice_id', sa.BigInteger(), nullable=True, comment='来源公告 ID'),
        sa.Column('user_id', sa.BigInteger(), nullable=False, comment='接收用户 ID'),
        sa.Column('sender_id', sa.BigInteger(), nullable=True, comment='发送人 ID'),
        sa.Column('title', sa.String(length=128), nullable=False, comment='消息标题'),
        sa.Column('content', sa.Text(), nullable=False, comment='消息内容'),
        sa.Column('message_type', sa.String(length=32), server_default='notice', nullable=False, comment='消息类型：notice=公告'),
        sa.Column('is_read', sa.Boolean(), server_default='false', nullable=False, comment='是否已读'),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True, comment='阅读时间'),
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='主键'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='更新时间'),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False, comment='软删除标记'),
        sa.Column('tenant_id', sa.BigInteger(), nullable=True, comment='租户ID（NULL=平台级）'),
        sa.PrimaryKeyConstraint('id'),
        comment='用户消息收件箱表',
    )
    op.create_index(op.f('ix_sys_user_message_notice_id'), 'sys_user_message', ['notice_id'], unique=False)
    op.create_index(op.f('ix_sys_user_message_sender_id'), 'sys_user_message', ['sender_id'], unique=False)
    op.create_index(op.f('ix_sys_user_message_tenant_id'), 'sys_user_message', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_sys_user_message_user_id'), 'sys_user_message', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_sys_user_message_user_id'), table_name='sys_user_message')
    op.drop_index(op.f('ix_sys_user_message_tenant_id'), table_name='sys_user_message')
    op.drop_index(op.f('ix_sys_user_message_sender_id'), table_name='sys_user_message')
    op.drop_index(op.f('ix_sys_user_message_notice_id'), table_name='sys_user_message')
    op.drop_table('sys_user_message')

    op.drop_index(op.f('ix_sys_notice_tenant_id'), table_name='sys_notice')
    op.drop_index(op.f('ix_sys_notice_publisher_id'), table_name='sys_notice')
    op.drop_table('sys_notice')
