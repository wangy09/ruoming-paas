"""add request_body response_body status_code to sys_audit_log

Revision ID: b1c2d3e4f5a6
Revises: 3a5ef7c3e7c0
Create Date: 2026-06-29 18:20:00.000000

Author: ruoming
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, None] = '3a5ef7c3e7c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'sys_audit_log',
        sa.Column(
            'request_body',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment='请求体数据（脱敏后）',
        ),
    )
    op.add_column(
        'sys_audit_log',
        sa.Column(
            'response_body',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment='响应体数据',
        ),
    )
    op.add_column(
        'sys_audit_log',
        sa.Column(
            'status_code',
            sa.Integer(),
            nullable=True,
            comment='HTTP 响应状态码',
        ),
    )


def downgrade() -> None:
    op.drop_column('sys_audit_log', 'status_code')
    op.drop_column('sys_audit_log', 'response_body')
    op.drop_column('sys_audit_log', 'request_body')
