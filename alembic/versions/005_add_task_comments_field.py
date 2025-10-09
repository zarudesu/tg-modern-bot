"""add task_comments field to task_reports

Revision ID: 005
Revises: 004
Create Date: 2025-10-07 14:00:00

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add task_comments column to task_reports table
    op.add_column(
        'task_reports',
        sa.Column(
            'task_comments',
            sa.Text(),
            nullable=True,
            comment='JSON массив комментариев из Plane (для формирования отчёта)'
        )
    )


def downgrade() -> None:
    # Remove task_comments column
    op.drop_column('task_reports', 'task_comments')
