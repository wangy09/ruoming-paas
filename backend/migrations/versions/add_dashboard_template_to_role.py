"""add dashboard_template to sys_role

Revision ID: add_dashboard_template_to_role
Revises: e8f9a0b1c2d3, 4f8a2d1c9e3b
Create Date: 2026-07-04

"""
from typing import Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "add_dashboard_template_to_role"
down_revision: Union[str, tuple[str, str], None] = ("e8f9a0b1c2d3", "4f8a2d1c9e3b")
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column(
        "sys_role",
        sa.Column(
            "dashboard_template",
            sa.String(length=32),
            nullable=True,
            comment="默认首页模板：platform/tenant/developer/personal，空=自动",
        ),
    )
    op.execute("UPDATE sys_role SET dashboard_template = 'tenant' WHERE code = 'tenant:admin'")
    op.execute("UPDATE sys_role SET dashboard_template = 'personal' WHERE code = 'tenant:user'")


def downgrade() -> None:
    op.drop_column("sys_role", "dashboard_template")
