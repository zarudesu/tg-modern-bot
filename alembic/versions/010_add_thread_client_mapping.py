"""Add thread support and client mapping

Revision ID: 010_thread_mapping
Revises: 009_chat_ai_tables
Create Date: 2026-01-26

Adds:
- thread_id column to chat_messages for topic support
- thread_client_mappings table: maps admin work group threads to client chats
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '010_thread_mapping'
down_revision = '009_chat_ai_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add thread_id to chat_messages
    op.add_column(
        'chat_messages',
        sa.Column('thread_id', sa.BigInteger(), nullable=True)
    )
    op.create_index(
        'idx_chat_messages_thread',
        'chat_messages',
        ['thread_id']
    )

    # 2. Create thread_client_mappings table
    op.create_table(
        'thread_client_mappings',
        sa.Column('id', sa.Integer(), primary_key=True),

        # Thread in admin work group
        sa.Column('work_group_id', sa.BigInteger(), nullable=False),  # Admin work group chat_id
        sa.Column('thread_id', sa.BigInteger(), nullable=False),  # Thread ID in work group
        sa.Column('thread_name', sa.String(255), nullable=True),  # Thread name for display

        # Client chat to monitor
        sa.Column('client_chat_id', sa.BigInteger(), nullable=False),  # Client's group chat_id
        sa.Column('client_name', sa.String(255), nullable=False),  # Client name (e.g., "DELTA")

        # Optional Plane integration
        sa.Column('plane_project_id', sa.String(100), nullable=True),

        # Status
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('created_by', sa.BigInteger(), nullable=True),  # Admin who created mapping

        # Indexes
        sa.Index('idx_thread_mapping_work_group', 'work_group_id'),
        sa.Index('idx_thread_mapping_thread', 'thread_id'),
        sa.Index('idx_thread_mapping_client', 'client_chat_id'),
    )

    # Unique constraint: one mapping per thread
    op.create_index(
        'idx_thread_mapping_unique',
        'thread_client_mappings',
        ['work_group_id', 'thread_id'],
        unique=True
    )


def downgrade() -> None:
    op.drop_table('thread_client_mappings')
    op.drop_index('idx_chat_messages_thread', 'chat_messages')
    op.drop_column('chat_messages', 'thread_id')
