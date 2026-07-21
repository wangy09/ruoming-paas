"""add_customer_order3_table

Revision ID: 75ff9152ca3a
Revises: 
Create Date: 2026-07-20 10:26:31

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '75ff9152ca3a'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'customer_order3',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=True),
        sa.Column('title', sa.String(255), nullable=True, comment='标题'),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_customer_order3_tenant_id', 'tenant_id'),
    )


def downgrade() -> None:
    op.drop_table('customer_order3')