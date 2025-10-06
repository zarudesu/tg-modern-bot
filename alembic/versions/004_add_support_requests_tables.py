"""add support requests tables

Revision ID: 004
Revises: 003
Create Date: 2025-01-10 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create chat_plane_mappings table
    op.create_table(
        'chat_plane_mappings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('chat_title', sa.String(length=255), nullable=True),
        sa.Column('chat_type', sa.String(length=50), nullable=False),
        sa.Column('plane_project_id', sa.String(length=100), nullable=False),
        sa.Column('plane_project_name', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('allow_all_users', sa.Boolean(), nullable=True),
        sa.Column('created_by', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_chat_plane_mappings_chat_id', 'chat_plane_mappings', ['chat_id'], unique=True)
    op.create_index('ix_chat_plane_mappings_plane_project_id', 'chat_plane_mappings', ['plane_project_id'], unique=False)
    op.create_index('ix_chat_plane_mappings_is_active', 'chat_plane_mappings', ['is_active'], unique=False)

    # Create support_requests table
    op.create_table(
        'support_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('user_name', sa.String(length=255), nullable=True),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('priority', sa.String(length=20), nullable=True),
        sa.Column('plane_project_id', sa.String(length=100), nullable=False),
        sa.Column('plane_issue_id', sa.String(length=100), nullable=True),
        sa.Column('plane_sequence_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('plane_created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['chat_id'], ['chat_plane_mappings.chat_id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_support_requests_chat_id', 'support_requests', ['chat_id'], unique=False)
    op.create_index('ix_support_requests_user_id', 'support_requests', ['user_id'], unique=False)
    op.create_index('ix_support_requests_plane_project_id', 'support_requests', ['plane_project_id'], unique=False)
    op.create_index('ix_support_requests_plane_issue_id', 'support_requests', ['plane_issue_id'], unique=False)
    op.create_index('ix_support_requests_status', 'support_requests', ['status'], unique=False)
    op.create_index('ix_support_requests_user_status', 'support_requests', ['user_id', 'status'], unique=False)
    op.create_index('ix_support_requests_created_at', 'support_requests', ['created_at'], unique=False)


def downgrade() -> None:
    # Drop support_requests table
    op.drop_index('ix_support_requests_created_at', table_name='support_requests')
    op.drop_index('ix_support_requests_user_status', table_name='support_requests')
    op.drop_index('ix_support_requests_status', table_name='support_requests')
    op.drop_index('ix_support_requests_plane_issue_id', table_name='support_requests')
    op.drop_index('ix_support_requests_plane_project_id', table_name='support_requests')
    op.drop_index('ix_support_requests_user_id', table_name='support_requests')
    op.drop_index('ix_support_requests_chat_id', table_name='support_requests')
    op.drop_table('support_requests')

    # Drop chat_plane_mappings table
    op.drop_index('ix_chat_plane_mappings_is_active', table_name='chat_plane_mappings')
    op.drop_index('ix_chat_plane_mappings_plane_project_id', table_name='chat_plane_mappings')
    op.drop_index('ix_chat_plane_mappings_chat_id', table_name='chat_plane_mappings')
    op.drop_table('chat_plane_mappings')
