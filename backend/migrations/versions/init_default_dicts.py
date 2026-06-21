"""init default dicts

Revision ID: init_default_dicts
Revises: create_dict_tables
Create Date: 2024-01-21

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'init_default_dicts'
down_revision = 'create_dict_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 插入字典类型
    op.execute("""
        INSERT INTO sys_dict_type (name, code, sort, status, is_system) VALUES
        ('用户状态', 'system_user_status', 1, 1, true),
        ('通用状态', 'system_common_status', 2, 1, true),
        ('数据权限范围', 'system_data_scope', 3, 1, true),
        ('租户状态', 'system_tenant_status', 4, 1, true),
        ('Agent状态', 'ai_agent_status', 5, 1, true)
    """)

    # 插入字典项
    op.execute("""
        INSERT INTO sys_dict_item (type_id, label, value, sort, status, is_default) VALUES
        -- 用户状态
        (1, '启用', 'true', 1, 1, true),
        (1, '禁用', 'false', 2, 1, false),
        -- 通用状态
        (2, '正常', '1', 1, 1, true),
        (2, '停用', '0', 2, 1, false),
        -- 数据权限范围
        (3, '全部数据', '1', 1, 1, true),
        (3, '本部门', '3', 2, 1, false),
        (3, '本部门及子部门', '2', 3, 1, false),
        (3, '仅本人', '4', 4, 1, false),
        (3, '自定义部门', '5', 5, 1, false),
        -- 租户状态
        (4, '正常', 'active', 1, 1, true),
        (4, '禁用', 'inactive', 2, 1, false),
        (4, '暂停', 'suspended', 3, 1, false),
        -- Agent状态
        (5, '草稿', 'draft', 1, 1, true),
        (5, '启用', 'active', 2, 1, false),
        (5, '归档', 'archived', 3, 1, false)
    """)


def downgrade() -> None:
    op.execute("DELETE FROM sys_dict_item WHERE type_id IN (1, 2, 3, 4, 5)")
    op.execute("DELETE FROM sys_dict_type WHERE code IN ('system_user_status', 'system_common_status', 'system_data_scope', 'system_tenant_status', 'ai_agent_status')")
