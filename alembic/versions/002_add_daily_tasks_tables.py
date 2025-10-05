"""Add daily tasks tables

Revision ID: 002
Revises: 001
Create Date: 2024-08-24 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add daily tasks tables"""
    
    # Создаем таблицу настроек админов для ежедневных задач
    op.create_table(
        'admin_daily_tasks_settings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('telegram_user_id', sa.BigInteger(), unique=True, nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, default=False),
        sa.Column('notification_time', sa.Time(), nullable=True),
        sa.Column('timezone', sa.String(length=50), nullable=False, default='Europe/Moscow'),
        sa.Column('include_overdue', sa.Boolean(), nullable=False, default=True),
        sa.Column('include_today', sa.Boolean(), nullable=False, default=True),
        sa.Column('include_upcoming', sa.Boolean(), nullable=False, default=True),
        sa.Column('group_by_project', sa.Boolean(), nullable=False, default=True),
        sa.Column('max_tasks_per_section', sa.Integer(), nullable=False, default=5),
        sa.Column('plane_email', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_sent_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('telegram_user_id')
    )
    
    # Создаем индексы для таблицы настроек
    op.create_index('ix_admin_daily_tasks_settings_telegram_user_id', 'admin_daily_tasks_settings', ['telegram_user_id'])
    op.create_index('ix_admin_daily_tasks_settings_enabled', 'admin_daily_tasks_settings', ['enabled'])
    op.create_index('ix_admin_daily_tasks_settings_notification_time', 'admin_daily_tasks_settings', ['notification_time'])
    
    # Создаем таблицу логов отправки ежедневных задач
    op.create_table(
        'daily_tasks_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('telegram_user_id', sa.BigInteger(), nullable=False),
        sa.Column('sent_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('total_tasks', sa.Integer(), nullable=False, default=0),
        sa.Column('overdue_tasks', sa.Integer(), nullable=False, default=0),
        sa.Column('today_tasks', sa.Integer(), nullable=False, default=0),
        sa.Column('upcoming_tasks', sa.Integer(), nullable=False, default=0),
        sa.Column('plane_response_time', sa.Integer(), nullable=True),
        sa.Column('tasks_data', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Создаем индексы для таблицы логов
    op.create_index('ix_daily_tasks_logs_telegram_user_id', 'daily_tasks_logs', ['telegram_user_id'])
    op.create_index('ix_daily_tasks_logs_sent_at', 'daily_tasks_logs', ['sent_at'])
    op.create_index('ix_daily_tasks_logs_success', 'daily_tasks_logs', ['success'])


def downgrade() -> None:
    """Drop daily tasks tables"""
    
    # Удаляем индексы
    op.drop_index('ix_daily_tasks_logs_success', table_name='daily_tasks_logs')
    op.drop_index('ix_daily_tasks_logs_sent_at', table_name='daily_tasks_logs')
    op.drop_index('ix_daily_tasks_logs_telegram_user_id', table_name='daily_tasks_logs')
    
    op.drop_index('ix_admin_daily_tasks_settings_notification_time', table_name='admin_daily_tasks_settings')
    op.drop_index('ix_admin_daily_tasks_settings_enabled', table_name='admin_daily_tasks_settings')
    op.drop_index('ix_admin_daily_tasks_settings_telegram_user_id', table_name='admin_daily_tasks_settings')
    
    # Удаляем таблицы
    op.drop_table('daily_tasks_logs')
    op.drop_table('admin_daily_tasks_settings')