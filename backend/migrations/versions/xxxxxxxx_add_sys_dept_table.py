"""add sys_dept table and data_scope_depts to sys_role

Revision ID: 5e7f2a9d
Revises: 3a5ef7c3e7c0
Create Date: 2026-06-18 14:00:00.000000

Author: ruoming
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = '5e7f2a9d'
down_revision: Union[str, None] = '3a5ef7c3e7c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)

    # 检查 sys_dept 表是否已存在
    existing_tables = inspector.get_table_names()

    if 'sys_dept' not in existing_tables:
        op.create_table(
            'sys_dept',
            sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('name', sa.String(length=64), nullable=False),
            sa.Column('parent_id', sa.BigInteger(), server_default='0', nullable=False),
            sa.Column('ancestors', sa.String(length=512), nullable=True),
            sa.Column('level', sa.Integer(), server_default='1', nullable=False),
            sa.Column('sort', sa.Integer(), server_default='0', nullable=False),
            sa.Column('leader', sa.String(length=32), nullable=True),
            sa.Column('leader_id', sa.BigInteger(), nullable=True),
            sa.Column('phone', sa.String(length=20), nullable=True),
            sa.Column('email', sa.String(length=128), nullable=True),
            sa.Column('status', sa.SmallInteger(), server_default='1', nullable=False),
            sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
            sa.Column('tenant_id', sa.BigInteger(), nullable=True),
            sa.Column('remark', sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_sys_dept_tenant_id', 'sys_dept', ['tenant_id'])
        op.create_index('ix_sys_dept_parent_id', 'sys_dept', ['parent_id'])

    # sys_role 表新增 data_scope_depts 字段
    role_columns = [c['name'] for c in inspector.get_columns('sys_role')]
    if 'data_scope_depts' not in role_columns:
        op.add_column('sys_role', sa.Column('data_scope_depts', sa.Text(), nullable=True))

    # sys_user 表新增 dept_id 字段
    user_columns = [c['name'] for c in inspector.get_columns('sys_user')]
    if 'dept_id' not in user_columns:
        op.add_column('sys_user', sa.Column('dept_id', sa.BigInteger(), nullable=True))


def downgrade() -> None:
    pass
