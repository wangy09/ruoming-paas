"""rename permission menu names

Revision ID: rename_perm_to_menu
Revises: add_is_system_to_perm
Create Date: 2024-01-20

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'rename_perm_to_menu'
down_revision = 'add_is_system_to_perm'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 更新菜单名称
    op.execute("""
        UPDATE sys_permission 
        SET name = '菜单管理' 
        WHERE code = 'system:permission:menu'
    """)
    
    # 更新按钮名称
    op.execute("""
        UPDATE sys_permission 
        SET name = CASE code
            WHEN 'system:permission:view' THEN '查询菜单'
            WHEN 'system:permission:create' THEN '新增菜单'
            WHEN 'system:permission:update' THEN '编辑菜单'
            WHEN 'system:permission:delete' THEN '删除菜单'
        END
        WHERE code IN ('system:permission:view', 'system:permission:create', 
                        'system:permission:update', 'system:permission:delete')
    """)


def downgrade() -> None:
    # 恢复原名
    op.execute("""
        UPDATE sys_permission 
        SET name = '权限管理' 
        WHERE code = 'system:permission:menu'
    """)
    
    op.execute("""
        UPDATE sys_permission 
        SET name = CASE code
            WHEN 'system:permission:view' THEN '查询权限'
            WHEN 'system:permission:create' THEN '新增权限'
            WHEN 'system:permission:update' THEN '编辑权限'
            WHEN 'system:permission:delete' THEN '删除权限'
        END
        WHERE code IN ('system:permission:view', 'system:permission:create', 
                        'system:permission:update', 'system:permission:delete')
    """)
