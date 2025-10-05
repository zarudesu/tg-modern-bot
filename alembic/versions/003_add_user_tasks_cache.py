"""Add user tasks cache table

Revision ID: 003
Revises: 002
Create Date: 2025-08-24 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add user tasks cache table"""
    op.create_table(
        'user_tasks_cache',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_email', sa.String(255), nullable=False, index=True),
        sa.Column('plane_task_id', sa.String(100), nullable=False),
        sa.Column('plane_project_id', sa.String(100), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('priority', sa.String(20), nullable=True, default='none'),
        sa.Column('project_name', sa.String(255), nullable=True),
        sa.Column('assignee_name', sa.String(255), nullable=True),
        sa.Column('assignee_email', sa.String(255), nullable=True),
        sa.Column('state_name', sa.String(100), nullable=True),
        sa.Column('sequence_id', sa.Integer(), nullable=True),
        sa.Column('due_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('plane_created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('plane_updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_overdue', sa.Boolean(), default=False),
        sa.Column('is_due_today', sa.Boolean(), default=False),
        sa.Column('cached_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        # Unique constraint for user_email + plane_task_id to prevent duplicates
        sa.UniqueConstraint('user_email', 'plane_task_id', name='uq_user_email_task_id')
    )
    
    # Add indexes for performance
    op.create_index('ix_user_tasks_cache_user_email', 'user_tasks_cache', ['user_email'])
    op.create_index('ix_user_tasks_cache_status', 'user_tasks_cache', ['status'])
    op.create_index('ix_user_tasks_cache_priority', 'user_tasks_cache', ['priority'])
    op.create_index('ix_user_tasks_cache_due_date', 'user_tasks_cache', ['due_date'])
    op.create_index('ix_user_tasks_cache_updated_at', 'user_tasks_cache', ['updated_at'])
    
    # Table for tracking sync status per user
    op.create_table(
        'user_tasks_sync_status',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_email', sa.String(255), nullable=False, unique=True),
        sa.Column('telegram_user_id', sa.BigInteger(), nullable=True),
        sa.Column('last_sync_started', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_sync_completed', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_sync_error', sa.Text(), nullable=True),
        sa.Column('sync_in_progress', sa.Boolean(), default=False),
        sa.Column('total_tasks_found', sa.Integer(), default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('ix_user_tasks_sync_status_user_email', 'user_tasks_sync_status', ['user_email'])
    op.create_index('ix_user_tasks_sync_status_telegram_user_id', 'user_tasks_sync_status', ['telegram_user_id'])


def downgrade() -> None:
    """Drop user tasks cache tables"""
    op.drop_table('user_tasks_sync_status')
    op.drop_table('user_tasks_cache')