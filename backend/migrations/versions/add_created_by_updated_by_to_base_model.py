"""add created_by and updated_by fields to all BaseModel tables

Revision ID: add_created_by_updated_by_to_base_model
Revises: add_gen_table_tables
Create Date: 2026-07-17 15:00:00.000000

Author: ruoming
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'add_created_by_updated_by'
down_revision: Union[str, None] = 'add_gen_table_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES_TO_UPDATE = [
    'sys_user',
    'sys_api_key',
    'sys_role',
    'sys_permission',
    'sys_column_permission',
    'sys_user_role',
    'sys_role_permission',
    'sys_user_permission',
    'sys_role_dept',
    'sys_config',
    'sys_file',
    'sys_integration_connection',
    'sys_external_identity',
    'sys_contact_sync_log',
    'sys_dept',
    'sys_dict_type',
    'sys_dict_item',
    'ai_conversation',
    'ai_entity_memory',
    'ai_key_value_memory',
    'ai_knowledge_base',
    'ai_agent',
    'ai_prompt_template',
    'ai_workflow',
]


def upgrade() -> None:
    from sqlalchemy import inspect
    
    conn = op.get_bind()
    inspector = inspect(conn)
    
    for table_name in TABLES_TO_UPDATE:
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
        except Exception as e:
            pass


def downgrade() -> None:
    for table_name in TABLES_TO_UPDATE:
        try:
            op.drop_column(table_name, 'created_by')
        except Exception:
            pass
        
        try:
            op.drop_column(table_name, 'updated_by')
        except Exception:
            pass
