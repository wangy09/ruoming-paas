"""add created_by and updated_by fields to missing BaseModel tables

Revision ID: add_created_by_updated_by_missing
Revises: add_created_by_updated_by
Create Date: 2026-07-17 16:00:00.000000

Author: ruoming
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'add_created_by_missing'
down_revision: Union[str, None] = 'add_created_by_updated_by'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MISSING_TABLES = [
    'sys_notice',
    'sys_user_message',
    'sys_audit_log',
    'sys_login_log',
    'sys_security_event',
    'sys_scheduled_task',
    'sys_task_execution_log',
    'sys_tenant',
    'sys_tenant_usage',
    'ai_model_config',
]


def upgrade() -> None:
    from sqlalchemy import inspect
    
    conn = op.get_bind()
    inspector = inspect(conn)
    
    for table_name in MISSING_TABLES:
        try:
            columns = [col['name'] for col in inspector.get_columns(table_name)]
            
            if 'created_by' not in columns:
                op.add_column(
                    table_name,
                    sa.Column('created_by', sa.BigInteger(), nullable=True, comment='创建人')
                )
            
            if 'updated_by' not in columns:
                op.add_column(
                    table_name,
                    sa.Column('updated_by', sa.BigInteger(), nullable=True, comment='更新人')
                )
        except Exception:
            pass


def downgrade() -> None:
    for table_name in MISSING_TABLES:
        try:
            op.drop_column(table_name, 'created_by')
        except Exception:
            pass
        
        try:
            op.drop_column(table_name, 'updated_by')
        except Exception:
            pass
