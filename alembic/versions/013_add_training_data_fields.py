"""Add training data fields to detected_issues

Revision ID: 013_training_data
Revises: 012_notify_task
Create Date: 2026-02-07
"""
from alembic import op
import sqlalchemy as sa

revision = '013_training_data'
down_revision = '012_notify_task'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('detected_issues', sa.Column('ai_response_json', sa.Text(), nullable=True))
    op.add_column('detected_issues', sa.Column('ai_model_used', sa.String(100), nullable=True))
    op.add_column('detected_issues', sa.Column('user_feedback', sa.String(50), nullable=True))
    op.add_column('detected_issues', sa.Column('user_edited_title', sa.String(255), nullable=True))
    op.add_column('detected_issues', sa.Column('user_edited_desc', sa.Text(), nullable=True))
    op.add_column('detected_issues', sa.Column('user_assigned_to', sa.String(255), nullable=True))
    op.add_column('detected_issues', sa.Column('feedback_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('detected_issues', sa.Column('correction_distance', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('detected_issues', 'correction_distance')
    op.drop_column('detected_issues', 'feedback_at')
    op.drop_column('detected_issues', 'user_assigned_to')
    op.drop_column('detected_issues', 'user_edited_desc')
    op.drop_column('detected_issues', 'user_edited_title')
    op.drop_column('detected_issues', 'user_feedback')
    op.drop_column('detected_issues', 'ai_model_used')
    op.drop_column('detected_issues', 'ai_response_json')
