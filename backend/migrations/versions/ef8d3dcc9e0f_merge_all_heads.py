"""merge all heads

Revision ID: ef8d3dcc9e0f
Revises: 75ff9152ca3a, add_tenant_id_to_role, add_updated_by_to_gen
Create Date: 2026-07-27 19:16:31.270656

Author: ruoming
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ef8d3dcc9e0f'
down_revision: Union[str, None] = ('75ff9152ca3a', 'add_tenant_id_to_role', 'add_updated_by_to_gen')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
