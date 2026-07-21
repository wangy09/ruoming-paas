"""add_{{ module_name }}_table

Revision ID: {{ migration_id }}
Revises: 
Create Date: {{ create_date }}

"""
from alembic import op
import sqlalchemy as sa
{% if has_jsonb %}from sqlalchemy.dialects import postgresql{% endif %}


# revision identifiers, used by Alembic.
revision = '{{ migration_id }}'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        '{{ table_name }}',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=True),
{% for field in migration_fields %}        sa.Column('{{ field.name }}', {{ field.type }}, {% if field.nullable %}nullable=True{% else %}nullable=False{% endif %}{% if field.default %}, server_default='{{ field.default }}'{% endif %}, comment='{{ field.comment }}'),
{% endfor %}        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_{{ table_name }}_tenant_id', 'tenant_id'),
    )


def downgrade() -> None:
    op.drop_table('{{ table_name }}')