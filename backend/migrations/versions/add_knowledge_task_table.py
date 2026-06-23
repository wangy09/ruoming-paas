"""add knowledge task table for reindex progress tracking

Revision ID: add_knowledge_task_table
Revises: add_upload_part_table
Create Date: 2026-06-22 01:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = 'add_knowledge_task_table'
down_revision = 'add_upload_part_table'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'ai_knowledge_task',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('task_id', sa.String(), nullable=False),
        sa.Column('kb_id', sa.BigInteger(), nullable=False),
        sa.Column('task_type', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('total', sa.Integer(), nullable=False),
        sa.Column('completed', sa.Integer(), nullable=False),
        sa.Column('failed', sa.Integer(), nullable=False),
        sa.Column('progress', sa.Integer(), nullable=False),
        sa.Column('current_doc', sa.String(), nullable=True),
        sa.Column('result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error_msg', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default='NOW()'),
        sa.Column('updated_at', sa.DateTime(), server_default='NOW()'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_knowledge_task_task_id', 'ai_knowledge_task', ['task_id'], unique=True)
    op.create_index('ix_knowledge_task_kb_id', 'ai_knowledge_task', ['kb_id'])


def downgrade() -> None:
    op.drop_index('ix_knowledge_task_kb_id', 'ai_knowledge_task')
    op.drop_index('ix_knowledge_task_task_id', 'ai_knowledge_task')
    op.drop_table('ai_knowledge_task')