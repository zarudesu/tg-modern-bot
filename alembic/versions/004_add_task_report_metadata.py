"""Add metadata fields to task_reports

Revision ID: 004
Revises: 003
Create Date: 2025-10-07

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add work metadata fields to task_reports table
    op.add_column('task_reports', sa.Column('work_duration', sa.String(50), nullable=True, comment="Длительность работы (напр. '2h', '4h')"))
    op.add_column('task_reports', sa.Column('is_travel', sa.Boolean(), nullable=True, comment="Выезд (True) или удалённо (False)"))
    op.add_column('task_reports', sa.Column('company', sa.String(255), nullable=True, comment="Компания/проект для которого выполнялась работа"))
    op.add_column('task_reports', sa.Column('workers', sa.Text(), nullable=True, comment="JSON массив исполнителей ['Имя1', 'Имя2']"))


def downgrade() -> None:
    # Remove work metadata fields from task_reports table
    op.drop_column('task_reports', 'workers')
    op.drop_column('task_reports', 'company')
    op.drop_column('task_reports', 'is_travel')
    op.drop_column('task_reports', 'work_duration')
