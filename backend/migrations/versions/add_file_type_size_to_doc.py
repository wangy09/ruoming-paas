"""add file_type and file_size to ai_knowledge_doc

Revision ID: add_file_type_size_to_doc
Revises: add_tenant_id_to_dict_item
Create Date: 2026-06-22 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_file_type_size_to_doc'
down_revision = 'add_tenant_id_to_dict_item'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'ai_knowledge_doc',
        sa.Column('file_type', sa.String(), nullable=True, comment='文件类型（扩展名）')
    )
    op.add_column(
        'ai_knowledge_doc',
        sa.Column('file_size', sa.Integer(), nullable=True, comment='文件大小（字节）')
    )


def downgrade() -> None:
    op.drop_column('ai_knowledge_doc', 'file_type')
    op.drop_column('ai_knowledge_doc', 'file_size')
