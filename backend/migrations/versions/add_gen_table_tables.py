"""add gen_table and gen_table_column tables

Revision ID: add_gen_table_tables
Revises: fa11ac597e03
Create Date: 2026-07-17 10:00:00.000000

Author: ruoming
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'add_gen_table_tables'
down_revision: Union[str, None] = '9e5f6a7b8c9d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'gen_table',
        sa.Column('table_name', sa.String(128), nullable=False, comment='数据库表名'),
        sa.Column('table_comment', sa.String(256), nullable=True, comment='表注释'),
        sa.Column('module_name', sa.String(64), nullable=False, comment='模块名'),
        sa.Column('entity_name', sa.String(64), nullable=False, comment='实体类名'),
        sa.Column('page_title', sa.String(64), nullable=True, comment='页面标题'),
        sa.Column('api_prefix', sa.String(128), nullable=True, comment='API 前缀'),
        sa.Column('author', sa.String(64), nullable=True, comment='作者'),
        sa.Column('status', sa.SmallInteger(), server_default='1', nullable=False, comment='状态：1启用 0禁用'),
        sa.Column('remark', sa.Text(), nullable=True, comment='备注'),
        sa.Column('created_by', sa.BigInteger(), nullable=True, comment='创建人 ID'),
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='主键'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='更新时间'),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False, comment='软删除标记'),
        sa.Column('tenant_id', sa.BigInteger(), nullable=True, comment='租户ID（NULL=平台级）'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_gen_table_table_name'), 'gen_table', ['table_name'], unique=False)
    op.create_index(op.f('ix_gen_table_tenant_id'), 'gen_table', ['tenant_id'], unique=False)

    op.create_table(
        'gen_table_column',
        sa.Column('table_id', sa.BigInteger(), nullable=False, comment='关联 gen_table.id'),
        sa.Column('column_name', sa.String(128), nullable=False, comment='字段名'),
        sa.Column('column_comment', sa.String(256), nullable=True, comment='字段注释'),
        sa.Column('data_type', sa.String(32), nullable=False, comment='数据库类型'),
        sa.Column('udt_name', sa.String(32), nullable=True, comment='UDT 名称'),
        sa.Column('is_nullable', sa.Boolean(), server_default='true', nullable=False, comment='是否可空'),
        sa.Column('is_primary_key', sa.Boolean(), server_default='false', nullable=False, comment='是否主键'),
        sa.Column('is_list', sa.Boolean(), server_default='true', nullable=False, comment='是否列表显示'),
        sa.Column('is_form', sa.Boolean(), server_default='true', nullable=False, comment='是否表单编辑'),
        sa.Column('is_search', sa.Boolean(), server_default='false', nullable=False, comment='是否搜索条件'),
        sa.Column('is_required', sa.Boolean(), server_default='false', nullable=False, comment='是否必填'),
        sa.Column('form_component', sa.String(32), server_default='input', nullable=False, comment='表单组件'),
        sa.Column('dict_type', sa.String(64), nullable=True, comment='字典类型编码'),
        sa.Column('sort', sa.Integer(), server_default='0', nullable=False, comment='显示排序'),
        sa.Column('created_by', sa.BigInteger(), nullable=True, comment='创建人 ID'),
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='主键'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='更新时间'),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False, comment='软删除标记'),
        sa.Column('tenant_id', sa.BigInteger(), nullable=True, comment='租户ID（NULL=平台级）'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_gen_table_column_table_id'), 'gen_table_column', ['table_id'], unique=False)
    op.create_index(op.f('ix_gen_table_column_tenant_id'), 'gen_table_column', ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_table('gen_table_column')
    op.drop_table('gen_table')