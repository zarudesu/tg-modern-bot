"""Add content_hash to detected_issues for deduplication

Revision ID: 011_content_hash
Revises: 010_thread_mapping
Create Date: 2026-02-07
"""
from alembic import op
import sqlalchemy as sa

revision = '011_content_hash'
down_revision = '010_thread_mapping'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'detected_issues',
        sa.Column('content_hash', sa.String(16), nullable=True)
    )
    op.create_index(
        'idx_detected_issues_content_hash',
        'detected_issues',
        ['content_hash']
    )


def downgrade() -> None:
    op.drop_index('idx_detected_issues_content_hash', table_name='detected_issues')
    op.drop_column('detected_issues', 'content_hash')
