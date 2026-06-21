"""add tenant_id to dict item

Revision ID: add_tenant_id_to_dict_item
Revises: init_default_dicts
Create Date: 2024-01-21

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_tenant_id_to_dict_item'
down_revision = 'init_default_dicts'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('sys_dict_item', sa.Column('tenant_id', sa.BigInteger(), nullable=True, comment='租户ID（NULL=平台级）'))
    op.create_index(op.f('ix_sys_dict_item_tenant_id'), 'sys_dict_item', ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_sys_dict_item_tenant_id'), table_name='sys_dict_item')
    op.drop_column('sys_dict_item', 'tenant_id')
