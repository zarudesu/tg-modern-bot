"""Add notify_task_created to chat_ai_settings

Revision ID: 012_notify_task
Revises: 011_content_hash
Create Date: 2026-02-07
"""
from alembic import op
import sqlalchemy as sa

revision = '012_notify_task'
down_revision = '011_content_hash'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'chat_ai_settings',
        sa.Column('notify_task_created', sa.Boolean(), server_default='false', nullable=True)
    )


def downgrade() -> None:
    op.drop_column('chat_ai_settings', 'notify_task_created')
