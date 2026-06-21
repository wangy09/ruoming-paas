"""create dict tables

Revision ID: create_dict_tables
Revises: rename_permission_to_menu
Create Date: 2024-01-21

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'create_dict_tables'
down_revision = 'rename_perm_to_menu'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 创建字典类型表
    op.create_table(
        'sys_dict_type',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=64), nullable=False, comment='字典类型名称'),
        sa.Column('code', sa.String(length=64), nullable=False, comment='字典类型编码'),
        sa.Column('description', sa.Text(), nullable=True, comment='描述'),
        sa.Column('sort', sa.Integer(), server_default='0', nullable=False, comment='排序'),
        sa.Column('status', sa.SmallInteger(), server_default='1', nullable=False, comment='状态：1正常 0停用'),
        sa.Column('is_system', sa.Boolean(), server_default='false', nullable=False, comment='是否系统内置'),
        sa.Column('tenant_id', sa.BigInteger(), nullable=True, comment='所属租户'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False, comment='逻辑删除'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'code', name='uq_tenant_dict_code'),
    )

    # 创建字典项表
    op.create_table(
        'sys_dict_item',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('type_id', sa.BigInteger(), nullable=False, comment='所属字典类型 ID'),
        sa.Column('label', sa.String(length=64), nullable=False, comment='显示标签'),
        sa.Column('value', sa.String(length=128), nullable=False, comment='实际值'),
        sa.Column('description', sa.Text(), nullable=True, comment='描述'),
        sa.Column('sort', sa.Integer(), server_default='0', nullable=False, comment='排序'),
        sa.Column('status', sa.SmallInteger(), server_default='1', nullable=False, comment='状态：1正常 0停用'),
        sa.Column('is_default', sa.Boolean(), server_default='false', nullable=False, comment='是否默认值'),
        sa.Column('css_class', sa.String(length=128), nullable=True, comment='样式类'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False, comment='逻辑删除'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('type_id', 'value', name='uq_type_item_value'),
        sa.ForeignKeyConstraint(['type_id'], ['sys_dict_type.id'], ondelete='CASCADE'),
    )


def downgrade() -> None:
    op.drop_table('sys_dict_item')
    op.drop_table('sys_dict_type')
