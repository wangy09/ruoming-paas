"""add memory features

Revision ID: 3cdf66d9a783
Revises: add_knowledge_task_table
Create Date: 2026-06-24 04:51:24.989994

Author: ruoming
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '3cdf66d9a783'
down_revision: Union[str, None] = 'add_knowledge_task_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands for memory features ###
    op.create_table('ai_entity_memory',
    sa.Column('conversation_id', sa.BigInteger(), nullable=False, comment='所属对话 ID'),
    sa.Column('entity_name', sa.String(), nullable=False, comment='实体名称'),
    sa.Column('entity_type', sa.String(), nullable=True, comment='实体类型：person/company/date/number/location/other'),
    sa.Column('entity_value', sa.String(), nullable=True, comment='实体值'),
    sa.Column('context', sa.Text(), nullable=True, comment='上下文描述'),
    sa.Column('source_message_id', sa.BigInteger(), nullable=True, comment='来源消息 ID'),
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='主键'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='创建时间'),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='更新时间'),
    sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False, comment='软删除标记'),
    sa.Column('tenant_id', sa.BigInteger(), nullable=True, comment='租户ID（NULL=平台级）'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ai_entity_memory_conversation_id'), 'ai_entity_memory', ['conversation_id'], unique=False)
    op.create_index(op.f('ix_ai_entity_memory_source_message_id'), 'ai_entity_memory', ['source_message_id'], unique=False)
    op.create_index(op.f('ix_ai_entity_memory_tenant_id'), 'ai_entity_memory', ['tenant_id'], unique=False)

    op.create_table('ai_kv_memory',
    sa.Column('conversation_id', sa.BigInteger(), nullable=False, comment='所属对话 ID'),
    sa.Column('key', sa.String(), nullable=False, comment='键'),
    sa.Column('value', sa.String(), nullable=True, comment='值（JSON 序列化）'),
    sa.Column('description', sa.String(), nullable=True, comment='描述'),
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='主键'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='创建时间'),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='更新时间'),
    sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False, comment='软删除标记'),
    sa.Column('tenant_id', sa.BigInteger(), nullable=True, comment='租户ID（NULL=平台级）'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ai_kv_memory_conversation_id'), 'ai_kv_memory', ['conversation_id'], unique=False)
    op.create_index(op.f('ix_ai_kv_memory_tenant_id'), 'ai_kv_memory', ['tenant_id'], unique=False)

    op.add_column('ai_conversation', sa.Column('memory_summary', sa.Text(), nullable=True, comment='记忆摘要（summary 模式使用）'))
    op.add_column('ai_message', sa.Column('embedding', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='消息内容的 embedding 向量（vector 记忆模式使用）'))
    op.add_column('ai_workflow_run', sa.Column('tenant_id', sa.BigInteger(), nullable=True, comment='租户 ID（用于多租户隔离）'))
    op.create_index(op.f('ix_ai_workflow_run_tenant_id'), 'ai_workflow_run', ['tenant_id'], unique=False)
    # ### end commands ###


def downgrade() -> None:
    # ### commands for memory features ###
    op.drop_index(op.f('ix_ai_workflow_run_tenant_id'), table_name='ai_workflow_run')
    op.drop_column('ai_workflow_run', 'tenant_id')
    op.drop_column('ai_message', 'embedding')
    op.drop_column('ai_conversation', 'memory_summary')

    op.drop_index(op.f('ix_ai_kv_memory_tenant_id'), table_name='ai_kv_memory')
    op.drop_index(op.f('ix_ai_kv_memory_conversation_id'), table_name='ai_kv_memory')
    op.drop_table('ai_kv_memory')

    op.drop_index(op.f('ix_ai_entity_memory_tenant_id'), table_name='ai_entity_memory')
    op.drop_index(op.f('ix_ai_entity_memory_source_message_id'), table_name='ai_entity_memory')
    op.drop_index(op.f('ix_ai_entity_memory_conversation_id'), table_name='ai_entity_memory')
    op.drop_table('ai_entity_memory')
    # ### end commands ###