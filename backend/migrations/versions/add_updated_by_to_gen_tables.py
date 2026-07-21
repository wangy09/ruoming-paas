"""add updated_by field to gen_table and gen_table_column

Revision ID: add_updated_by_to_gen
Revises: add_created_by_missing
Create Date: 2026-07-17 17:00:00.000000

Author: ruoming
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'add_updated_by_to_gen'
down_revision: Union[str, None] = 'add_created_by_missing'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from sqlalchemy import inspect
    
    conn = op.get_bind()
    inspector = inspect(conn)
    
    for table_name in ['gen_table', 'gen_table_column']:
        try:
            columns = [col['name'] for col in inspector.get_columns(table_name)]
            
            if 'updated_by' not in columns:
                op.add_column(
                    table_name,
                    sa.Column('updated_by', sa.BigInteger(), nullable=True, comment='更新人')
                )
        except Exception:
            pass


def downgrade() -> None:
    for table_name in ['gen_table', 'gen_table_column']:
        try:
            op.drop_column(table_name, 'updated_by')
        except Exception:
            pass
