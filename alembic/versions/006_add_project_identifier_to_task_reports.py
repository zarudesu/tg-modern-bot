"""Add project_identifier to task_reports

Revision ID: 006_add_project_identifier
Revises: 005_add_task_comments_field
Create Date: 2025-10-14 14:50:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '006_add_project_identifier'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade():
    # Add project_identifier column to task_reports (idempotent)
    # Use raw SQL with IF NOT EXISTS for safety
    from sqlalchemy import text
    connection = op.get_bind()
    connection.execute(text("""
        ALTER TABLE task_reports
        ADD COLUMN IF NOT EXISTS project_identifier VARCHAR(20);
    """))

    # Add comment if column exists
    connection.execute(text("""
        COMMENT ON COLUMN task_reports.project_identifier IS 'Префикс проекта (HARZL, HHIVP, и т.д.)';
    """))


def downgrade():
    # Remove project_identifier column
    op.drop_column('task_reports', 'project_identifier')
