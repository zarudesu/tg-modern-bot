"""Add Yaroslav Poslov as admin with all mappings

Revision ID: 014_add_yaroslav
Revises: 013_add_training_data_fields
Create Date: 2026-02-09

Adds:
- Yaroslav to plane_telegram_mappings (5 lookup keys)
- Yaroslav to admin_daily_tasks_settings
- Yaroslav to work_journal_workers
"""
from alembic import op
import sqlalchemy as sa

revision = '014_add_yaroslav'
down_revision = '013_add_training_data_fields'
branch_labels = None
depends_on = None

TELEGRAM_ID = 449320695
USERNAME = 'cernezvratky'
DISPLAY_NAME = 'Ярослав Послов'
SHORT_NAME = 'Ярослав'
GROUP_HANDLE = '@cernezvratky'
PLANE_EMAIL = 'poslov.yaroslav@gmail.com'


def upgrade() -> None:
    conn = op.get_bind()

    # 1. plane_telegram_mappings
    mappings = [
        ('Ярослав Послов', PLANE_EMAIL),
        ('Ярослав', None),
        ('Poslov Yaroslav', PLANE_EMAIL),
        ('poslov.yaroslav', PLANE_EMAIL),
        (PLANE_EMAIL, PLANE_EMAIL),
    ]
    for lookup_key, email in mappings:
        result = conn.execute(
            sa.text("SELECT id FROM plane_telegram_mappings WHERE lookup_key = :key"),
            {"key": lookup_key}
        )
        if result.fetchone() is None:
            conn.execute(
                sa.text("""
                    INSERT INTO plane_telegram_mappings
                    (lookup_key, telegram_id, telegram_username, display_name, plane_email, short_name, group_handle, is_active)
                    VALUES (:key, :tid, :uname, :dname, :email, :sname, :handle, true)
                """),
                {"key": lookup_key, "tid": TELEGRAM_ID, "uname": USERNAME,
                 "dname": DISPLAY_NAME, "email": email, "sname": SHORT_NAME, "handle": GROUP_HANDLE}
            )

    # 2. admin_daily_tasks_settings
    result = conn.execute(
        sa.text("SELECT id FROM admin_daily_tasks_settings WHERE telegram_user_id = :tid"),
        {"tid": TELEGRAM_ID}
    )
    if result.fetchone() is None:
        conn.execute(
            sa.text("""
                INSERT INTO admin_daily_tasks_settings
                (telegram_user_id, enabled, plane_email, timezone, notification_time,
                 include_overdue, include_today, include_upcoming, group_by_project,
                 max_tasks_per_section, created_at, updated_at)
                VALUES (:tid, false, :email, 'Europe/Moscow', '09:00:00',
                        true, true, true, true, 5, NOW(), NOW())
            """),
            {"tid": TELEGRAM_ID, "email": PLANE_EMAIL}
        )

    # 3. work_journal_workers
    result = conn.execute(
        sa.text("SELECT id FROM work_journal_workers WHERE name = :name"),
        {"name": SHORT_NAME}
    )
    if result.fetchone() is None:
        conn.execute(
            sa.text("""
                INSERT INTO work_journal_workers
                (name, telegram_username, telegram_user_id, mention_enabled, display_order, is_active, created_at)
                VALUES (:name, :uname, :tid, true, 4, true, NOW())
            """),
            {"name": SHORT_NAME, "uname": USERNAME, "tid": TELEGRAM_ID}
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM plane_telegram_mappings WHERE telegram_id = :tid"),
        {"tid": TELEGRAM_ID}
    )
    conn.execute(
        sa.text("DELETE FROM admin_daily_tasks_settings WHERE telegram_user_id = :tid"),
        {"tid": TELEGRAM_ID}
    )
    conn.execute(
        sa.text("DELETE FROM work_journal_workers WHERE telegram_user_id = :tid"),
        {"tid": TELEGRAM_ID}
    )
