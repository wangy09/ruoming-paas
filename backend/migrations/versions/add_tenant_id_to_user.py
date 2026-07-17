"""add tenant_id to sys_user

Revision ID: add_tenant_id_to_user
Revises: 3a5ef7c3e7c0
Create Date: 2026-07-16

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_tenant_id_to_user'
down_revision = '3a5ef7c3e7c0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('sys_user', sa.Column('tenant_id', sa.BigInteger(), nullable=True, comment='所属租户 ID'))
    op.create_index(op.f('ix_sys_user_tenant_id'), 'sys_user', ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_sys_user_tenant_id'), table_name='sys_user')
    op.drop_column('sys_user', 'tenant_id')