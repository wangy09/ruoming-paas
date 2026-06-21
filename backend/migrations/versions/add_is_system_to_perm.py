"""add is_system to sys_permission

Revision ID: add_is_system_to_perm
Revises: add_level_to_dept
Create Date: 2024-01-20

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_is_system_to_perm'
down_revision = 'add_level_to_dept'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 添加 is_system 字段到 sys_permission 表
    op.add_column(
        'sys_permission',
        sa.Column('is_system', sa.Boolean(), nullable=False, server_default='false', comment='是否系统内置权限（不可删除）')
    )


def downgrade() -> None:
    # 移除 is_system 字段
    op.drop_column('sys_permission', 'is_system')
