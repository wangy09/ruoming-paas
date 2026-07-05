"""expand user avatar url length

Revision ID: 9d4e5f6a7b8c
Revises: 8c3d4e5f6a7b
Create Date: 2026-07-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9d4e5f6a7b8c"
down_revision: Union[str, None] = "8c3d4e5f6a7b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "sys_user",
        "avatar",
        existing_type=sa.String(length=256),
        type_=sa.String(length=1024),
        existing_nullable=True,
        existing_comment="头像 URL",
    )


def downgrade() -> None:
    op.alter_column(
        "sys_user",
        "avatar",
        existing_type=sa.String(length=1024),
        type_=sa.String(length=256),
        existing_nullable=True,
        existing_comment="头像 URL",
    )
