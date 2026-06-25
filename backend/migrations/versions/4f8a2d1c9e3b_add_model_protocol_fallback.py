"""add model_config protocol and fallback fields

Revision ID: 4f8a2d1c9e3b
Revises: 3cdf66d9a783
Create Date: 2026-06-24 12:00:00.000000

Author: ruoming
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '4f8a2d1c9e3b'
down_revision: Union[str, None] = '3cdf66d9a783'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ai_model_config 表缺少的字段
    op.add_column('ai_model_config', sa.Column('protocol', sa.String(), server_default='openai_compat', nullable=False, comment='通信协议：openai_compat / anthropic / gemini'))
    op.add_column('ai_model_config', sa.Column('is_fallback', sa.Boolean(), server_default='false', nullable=False, comment='是否为熔断备用模型（主力模型不可用时自动切换）'))
    op.alter_column('ai_model_config', 'provider',
               existing_type=sa.VARCHAR(),
               comment='厂商标识（自由填写：openai/qwen/doubao/deepseek/ollama 等）',
               existing_nullable=False)


def downgrade() -> None:
    op.alter_column('ai_model_config', 'provider',
               existing_type=sa.VARCHAR(),
               comment='提供商标识：zhuilu / openai / ollama',
               existing_nullable=False)
    op.drop_column('ai_model_config', 'is_fallback')
    op.drop_column('ai_model_config', 'protocol')
