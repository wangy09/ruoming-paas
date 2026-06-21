"""add missing level column to sys_dept

Revision ID: add_level_to_dept
Revises: 5e7f2a9d
Create Date: 2026-06-20 14:00:00.000000

Author: ruoming
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = 'add_level_to_dept'
down_revision: Union[str, None] = '5e7f2a9d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    
    dept_columns = [c['name'] for c in inspector.get_columns('sys_dept')]
    
    if 'level' not in dept_columns:
        op.add_column('sys_dept', sa.Column('level', sa.Integer(), server_default='1', nullable=False))
    
    if 'leader_id' not in dept_columns:
        op.add_column('sys_dept', sa.Column('leader_id', sa.BigInteger(), nullable=True))


def downgrade() -> None:
    pass
