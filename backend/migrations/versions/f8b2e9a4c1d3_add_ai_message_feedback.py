"""add ai_message_feedback

Revision ID: f8b2e9a4c1d3
Revises: 8a38579c7a3a
Create Date: 2026-07-30 12:00:00.000000

Author: ruoming
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f8b2e9a4c1d3'
down_revision: Union[str, None] = '8a38579c7a3a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('ai_message_feedback',
    # 系统反馈核心字段
    sa.Column('title', sa.String(length=200), nullable=False, comment='反馈标题'),
    sa.Column('category', sa.String(length=32), nullable=False, comment='反馈分类：bug/feature/usage/other'),
    sa.Column('content', sa.Text(), nullable=False, comment='详细反馈内容'),
    sa.Column('severity', sa.String(length=16), nullable=True, comment='严重程度：low/medium/high/critical'),
    # 可选关联字段
    sa.Column('message_id', sa.BigInteger(), nullable=True, comment='关联的 AI 消息 ID（AI 相关问题时）'),
    sa.Column('conversation_id', sa.BigInteger(), nullable=True, comment='所属对话 ID（可选）'),
    sa.Column('agent_id', sa.BigInteger(), nullable=True, comment='关联的 Agent ID'),
    # 用户信息
    sa.Column('user_id', sa.BigInteger(), nullable=False, comment='反馈用户 ID'),
    # 其他可选字段
    sa.Column('rating', sa.SmallInteger(), nullable=True, comment='评价：1=点赞，-1=点踩（可选）'),
    sa.Column('tags', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='反馈标签数组'),
    sa.Column('screenshot_url', sa.String(length=500), nullable=True, comment='截图 URL'),
    # 处理状态
    sa.Column('status', sa.String(), server_default='pending', nullable=False, comment='处理状态：pending/resolved/ignored'),
    sa.Column('reply', sa.Text(), nullable=True, comment='管理员回复'),
    sa.Column('replied_by', sa.BigInteger(), nullable=True, comment='回复人 ID'),
    sa.Column('replied_at', sa.DateTime(timezone=True), nullable=True),
    # 主键 & 审计字段
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='主键'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='创建时间'),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='更新时间'),
    sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False, comment='软删除标记'),
    sa.Column('tenant_id', sa.BigInteger(), nullable=True, comment='租户ID（NULL=平台级）'),
    sa.Column('created_by', sa.BigInteger(), nullable=True, comment='创建人'),
    sa.Column('updated_by', sa.BigInteger(), nullable=True, comment='更新人'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ai_message_feedback_message_id'), 'ai_message_feedback', ['message_id'], unique=False)
    op.create_index(op.f('ix_ai_message_feedback_conversation_id'), 'ai_message_feedback', ['conversation_id'], unique=False)
    op.create_index(op.f('ix_ai_message_feedback_agent_id'), 'ai_message_feedback', ['agent_id'], unique=False)
    op.create_index(op.f('ix_ai_message_feedback_user_id'), 'ai_message_feedback', ['user_id'], unique=False)
    op.create_index(op.f('ix_ai_message_feedback_category'), 'ai_message_feedback', ['category'], unique=False)
    op.create_index(op.f('ix_ai_message_feedback_tenant_id'), 'ai_message_feedback', ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_ai_message_feedback_tenant_id'), table_name='ai_message_feedback')
    op.drop_index(op.f('ix_ai_message_feedback_category'), table_name='ai_message_feedback')
    op.drop_index(op.f('ix_ai_message_feedback_user_id'), table_name='ai_message_feedback')
    op.drop_index(op.f('ix_ai_message_feedback_agent_id'), table_name='ai_message_feedback')
    op.drop_index(op.f('ix_ai_message_feedback_conversation_id'), table_name='ai_message_feedback')
    op.drop_index(op.f('ix_ai_message_feedback_message_id'), table_name='ai_message_feedback')
    op.drop_table('ai_message_feedback')
