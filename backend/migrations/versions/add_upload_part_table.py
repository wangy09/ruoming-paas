"""add upload_part table for multipart upload

Revision ID: add_upload_part_table
Revises: add_storage_fields_to_doc
Create Date: 2026-06-22 01:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_upload_part_table'
down_revision = 'add_storage_fields_to_doc'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'ai_knowledge_upload_part',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('upload_id', sa.String(), nullable=False),
        sa.Column('kb_id', sa.BigInteger(), nullable=False),
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('file_hash', sa.String(), nullable=False),
        sa.Column('part_number', sa.Integer(), nullable=False),
        sa.Column('part_size', sa.Integer(), nullable=False),
        sa.Column('part_hash', sa.String(), nullable=False),
        sa.Column('storage_key', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default='NOW()'),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_upload_part_upload_id', 'ai_knowledge_upload_part', ['upload_id'])
    op.create_index('ix_upload_part_kb_id', 'ai_knowledge_upload_part', ['kb_id'])


def downgrade() -> None:
    op.drop_index('ix_upload_part_kb_id', 'ai_knowledge_upload_part')
    op.drop_index('ix_upload_part_upload_id', 'ai_knowledge_upload_part')
    op.drop_table('ai_knowledge_upload_part')