"""Add project_identifier to task_reports

Revision ID: 006_add_project_identifier
Revises: 005_add_task_comments_field
Create Date: 2025-10-14 14:50:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '006_add_project_identifier'
down_revision = '005_add_task_comments_field'
branch_labels = None
depends_on = None


def upgrade():
    # Add project_identifier column to task_reports
    op.add_column(
        'task_reports',
        sa.Column(
            'project_identifier',
            sa.String(length=20),
            nullable=True,
            comment='Префикс проекта (HARZL, HHIVP, и т.д.)'
        )
    )


def downgrade():
    # Remove project_identifier column
    op.drop_column('task_reports', 'project_identifier')
