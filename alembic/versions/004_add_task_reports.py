"""add task_reports table

Revision ID: 004
Revises: 003
Create Date: 2025-10-07 03:00:00

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
    # Создание таблицы task_reports
    op.create_table(
        'task_reports',
        sa.Column('id', sa.Integer(), nullable=False),

        # Связь с Support Request
        sa.Column('support_request_id', sa.Integer(), nullable=True, comment='Связь с заявкой поддержки (если есть)'),

        # Plane Task Information
        sa.Column('plane_issue_id', sa.String(length=255), nullable=False, comment='UUID задачи в Plane'),
        sa.Column('plane_sequence_id', sa.Integer(), nullable=True, comment='Номер задачи (HHIVP-123)'),
        sa.Column('plane_project_id', sa.String(length=255), nullable=True, comment='UUID проекта в Plane'),
        sa.Column('task_title', sa.String(length=500), nullable=True, comment='Название задачи'),
        sa.Column('task_description', sa.Text(), nullable=True, comment='Описание задачи (для контекста)'),

        # Кто закрыл задачу
        sa.Column('closed_by_plane_name', sa.String(length=255), nullable=True, comment='Имя из Plane (display_name / first_name)'),
        sa.Column('closed_by_telegram_username', sa.String(length=255), nullable=True, comment='Telegram username (@zardes) после маппинга'),
        sa.Column('closed_by_telegram_id', sa.BigInteger(), nullable=True, comment='Telegram User ID админа (приоритет для напоминаний)'),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True, comment='Когда задача была закрыта в Plane'),

        # Отчёт
        sa.Column('report_text', sa.Text(), nullable=True, comment='Текст отчёта для клиента (что было сделано)'),
        sa.Column('report_submitted_by', sa.BigInteger(), nullable=True, comment='Telegram user_id админа, который заполнил отчёт'),
        sa.Column('report_submitted_at', sa.DateTime(timezone=True), nullable=True, comment='Когда отчёт был заполнен'),

        # Интеграция с Work Journal
        sa.Column('work_journal_entry_id', sa.Integer(), nullable=True, comment='Связь с записью work journal (опционально)'),
        sa.Column('auto_filled_from_journal', sa.Boolean(), default=False, comment='Был ли отчёт автоматически заполнен из work journal'),

        # Статусы
        sa.Column('status', sa.String(length=50), nullable=False, server_default='pending', comment='pending → draft → approved → sent_to_client'),

        # Система напоминаний
        sa.Column('reminder_count', sa.Integer(), nullable=False, server_default='0', comment='Сколько напоминаний отправлено'),
        sa.Column('last_reminder_at', sa.DateTime(timezone=True), nullable=True, comment='Когда последнее напоминание отправлено'),
        sa.Column('reminder_level', sa.Integer(), server_default='0', comment='Уровень агрессивности напоминаний (0-3)'),

        # Клиент
        sa.Column('client_chat_id', sa.BigInteger(), nullable=True, comment='Chat ID где создавалась заявка'),
        sa.Column('client_user_id', sa.BigInteger(), nullable=True, comment='User ID клиента (опционально)'),
        sa.Column('client_message_id', sa.BigInteger(), nullable=True, comment='ID исходного сообщения заявки (для reply)'),
        sa.Column('client_notified_at', sa.DateTime(timezone=True), nullable=True, comment='Когда клиенту отправлен отчёт'),

        # Метаданные
        sa.Column('webhook_payload', sa.Text(), nullable=True, comment='JSON payload от n8n webhook (для дебага)'),
        sa.Column('error_message', sa.Text(), nullable=True, comment='Сообщение об ошибке если что-то пошло не так'),
        sa.Column('notes', sa.Text(), nullable=True, comment='Внутренние заметки (не видны клиенту)'),

        # Временные метки
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'), comment='Когда создан TaskReport'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'), comment='Последнее обновление'),

        # Primary Key
        sa.PrimaryKeyConstraint('id'),

        # Foreign Keys
        sa.ForeignKeyConstraint(['support_request_id'], ['support_requests.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['work_journal_entry_id'], ['work_journal_entries.id'], ondelete='SET NULL'),
    )

    # Индексы
    op.create_index('idx_task_reports_status', 'task_reports', ['status'])
    op.create_index('idx_task_reports_pending', 'task_reports', ['status', 'closed_by_telegram_id'])
    op.create_index('idx_task_reports_reminders', 'task_reports', ['status', 'last_reminder_at'])
    op.create_index('idx_task_reports_client', 'task_reports', ['client_chat_id', 'created_at'])
    op.create_index('idx_task_reports_plane_issue', 'task_reports', ['plane_issue_id'], unique=True)
    op.create_index('idx_task_reports_support_request', 'task_reports', ['support_request_id'])
    op.create_index('idx_task_reports_closed_by', 'task_reports', ['closed_by_telegram_id'])


def downgrade() -> None:
    # Удаление индексов
    op.drop_index('idx_task_reports_closed_by', table_name='task_reports')
    op.drop_index('idx_task_reports_support_request', table_name='task_reports')
    op.drop_index('idx_task_reports_plane_issue', table_name='task_reports')
    op.drop_index('idx_task_reports_client', table_name='task_reports')
    op.drop_index('idx_task_reports_reminders', table_name='task_reports')
    op.drop_index('idx_task_reports_pending', table_name='task_reports')
    op.drop_index('idx_task_reports_status', table_name='task_reports')

    # Удаление таблицы
    op.drop_table('task_reports')
