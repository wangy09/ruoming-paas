"""add tenant_id to sys_role

Revision ID: add_tenant_id_to_role
Revises: add_tenant_id_to_user
Create Date: 2026-07-16

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_tenant_id_to_role'
down_revision = 'add_tenant_id_to_user'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('sys_role', sa.Column('tenant_id', sa.BigInteger(), nullable=True, comment='所属租户 ID（NULL=平台级）'))
    op.create_index(op.f('ix_sys_role_tenant_id'), 'sys_role', ['tenant_id'], unique=False)
    op.drop_constraint('sys_role_code_key', 'sys_role', type_='unique')
    op.create_unique_constraint('uq_tenant_role_code', 'sys_role', ['tenant_id', 'code'])


def downgrade() -> None:
    op.drop_constraint('uq_tenant_role_code', 'sys_role', type_='unique')
    op.create_unique_constraint('sys_role_code_key', 'sys_role', ['code'])
    op.drop_index(op.f('ix_sys_role_tenant_id'), table_name='sys_role')
    op.drop_column('sys_role', 'tenant_id')