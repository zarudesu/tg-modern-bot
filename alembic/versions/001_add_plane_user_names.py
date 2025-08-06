"""Add plane_user_names to work_journal_workers

Revision ID: 001_plane_users
Revises: 
Create Date: 2025-08-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TEXT

# revision identifiers
revision = '001_plane_users'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add plane_user_names column to work_journal_workers table"""
    
    # Добавляем новый столбец
    op.add_column('work_journal_workers', 
                  sa.Column('plane_user_names', TEXT, nullable=True))
    
    # Заполняем данными для существующих пользователей
    connection = op.get_bind()
    
    # Обновляем данные для Дмитрия Гусева
    connection.execute(
        sa.text("""
            UPDATE work_journal_workers 
            SET plane_user_names = '["Dmitriy Gusev", "Dmitry Gusev", "Dima Gusev"]'
            WHERE name = 'Гусев Дима'
        """)
    )
    
    # Обновляем данные для Тимофея
    connection.execute(
        sa.text("""
            UPDATE work_journal_workers 
            SET plane_user_names = '["Тимофей Батырев", "Timofeij Batyrev"]'
            WHERE name = 'Тимофей Батырев'
        """)
    )
    
    # Обновляем данные для Константина
    connection.execute(
        sa.text("""
            UPDATE work_journal_workers 
            SET plane_user_names = '["Konstantin Makeykin", "Kostya Makeykin", "Константин Макейкин"]'
            WHERE name = 'Константин Макейкин'
        """)
    )


def downgrade() -> None:
    """Remove plane_user_names column from work_journal_workers table"""
    op.drop_column('work_journal_workers', 'plane_user_names')
