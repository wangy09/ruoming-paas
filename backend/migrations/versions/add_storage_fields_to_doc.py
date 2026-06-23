"""add storage fields to ai_knowledge_doc

Revision ID: add_storage_fields_to_doc
Revises: add_file_type_size_to_doc
Create Date: 2026-06-22 00:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_storage_fields_to_doc'
down_revision = 'add_file_type_size_to_doc'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'ai_knowledge_doc',
        sa.Column('storage_backend', sa.String(), nullable=True, comment='存储后端：local / oss / minio')
    )
    op.add_column(
        'ai_knowledge_doc',
        sa.Column('storage_key', sa.String(), nullable=True, comment='存储对象 key')
    )
    op.add_column(
        'ai_knowledge_doc',
        sa.Column('storage_url', sa.Text(), nullable=True, comment='存储访问 URL')
    )


def downgrade() -> None:
    op.drop_column('ai_knowledge_doc', 'storage_url')
    op.drop_column('ai_knowledge_doc', 'storage_key')
    op.drop_column('ai_knowledge_doc', 'storage_backend')
