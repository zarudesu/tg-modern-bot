"""Extend plane_telegram_mappings with short_name and group_handle, seed all companies

Revision ID: 008_extend_mappings
Revises: 007_plane_mappings
Create Date: 2026-01-23

Adds:
- short_name column to plane_telegram_mappings (e.g., "Костя")
- group_handle column to plane_telegram_mappings (e.g., "@gendir_hhivp")
- All companies from COMPANY_MAPPING to company_mappings table
- Updates existing telegram mappings with short_name and group_handle
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '008_extend_mappings'
down_revision = '007_plane_mappings'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add new columns to plane_telegram_mappings
    op.add_column('plane_telegram_mappings',
        sa.Column('short_name', sa.String(100), nullable=True)
    )
    op.add_column('plane_telegram_mappings',
        sa.Column('group_handle', sa.String(100), nullable=True)
    )

    # 2. Update existing telegram mappings with short_name and group_handle
    _update_telegram_mappings()

    # 3. Seed all companies (only if not exists)
    _seed_all_companies()


def _update_telegram_mappings():
    """Update existing telegram mappings with short_name and group_handle"""
    conn = op.get_bind()

    # Define updates: telegram_id -> (short_name, group_handle)
    updates = {
        28795547: ('Костя', '@zardes'),          # Zardes
        132228544: ('Дима', '@gendir_hhivp'),     # Dima Gusev
        56994156: ('Тимофей', '@spiritphoto'),    # Timofey Batyrev
    }

    for telegram_id, (short_name, group_handle) in updates.items():
        conn.execute(
            sa.text("""
                UPDATE plane_telegram_mappings
                SET short_name = :short_name, group_handle = :group_handle
                WHERE telegram_id = :telegram_id
            """),
            {"telegram_id": telegram_id, "short_name": short_name, "group_handle": group_handle}
        )


def _seed_all_companies():
    """Seed all companies from COMPANY_MAPPING"""
    conn = op.get_bind()

    # All companies: (plane_project_name, display_name_ru, display_name_en)
    companies = [
        # Main companies
        ('HarzLabs', 'Харц Лабз', 'HarzLabs'),
        ('3D.RU', '3Д.РУ', '3D.RU'),
        ('Garden of Health', 'Сад Здоровья', 'Garden of Health'),
        ('Сад Здоровья', 'Сад Здоровья', 'Garden of Health'),
        ('Delta', 'Дельта', 'Delta'),
        ('АО Дельта', 'Дельта', 'Delta'),
        ('Moiseev', 'Моисеев', 'Moiseev'),
        ('ИП Моисеев', 'Моисеев', 'Moiseev'),
        ('Stifter', 'Стифтер', 'Stifter'),
        ('Стифтер Хаус', 'Стифтер', 'Stifter'),
        ('Vekha', 'Веха', 'Vekha'),
        ('УК Веха', 'Веха', 'Vekha'),
        ('Sosnovy Bor', 'Сосновый бор', 'Sosnovy Bor'),
        ('Сосновый Бор', 'Сосновый бор', 'Sosnovy Bor'),
        ('Bibirevo', 'Бибирево', 'Bibirevo'),
        ('Romashka', 'Ромашка', 'Romashka'),
        ('Ромашка', 'Ромашка', 'Romashka'),
        ('Vyoshki 95', 'Вёшки 95', 'Vyoshki 95'),
        ('Vondiga Park', 'Вондига Парк', 'Vondiga Park'),
        ('Вондига Парк', 'Вондига Парк', 'Vondiga Park'),
        ('Iva', 'Ива', 'Iva'),
        ('Ива', 'Ива', 'Iva'),
        ('CifraCifra', 'ЦифраЦифра', 'CifraCifra'),
        ('ЦифраЦифра', 'ЦифраЦифра', 'CifraCifra'),

        # Additional projects
        ('hhivp and all', 'HHIVP', 'HHIVP'),
        ('HHIVP', 'HHIVP', 'HHIVP'),
        ('Бастион (Алтушка 41 каб 101)', 'Бастион', 'Bastion'),
        ('Бастион', 'Бастион', 'Bastion'),
        ('Банком', 'Банком', 'Bankom'),
        ('reg.ru', 'Reg.ru', 'Reg.ru'),
        ('web-разработка', 'Web-разработка', 'Web Development'),

        # From migration 007 (ensure they exist)
        ('HARZL', 'ХАРЗЛ', 'HARZL'),
        ('DELTA', 'ДЕЛЬТА', 'DELTA'),
        ('INFOTECS', 'Инфотекс', 'Infotecs'),
        ('GAZPROM', 'Газпром', 'Gazprom'),
        ('ROGA', 'Рога и Копыта', 'Roga'),
        ('INTERNAL', 'Внутренние задачи', 'Internal'),
    ]

    for plane_name, ru_name, en_name in companies:
        # Check if already exists
        result = conn.execute(
            sa.text("SELECT id FROM company_mappings WHERE plane_project_name = :name"),
            {"name": plane_name}
        )
        if result.fetchone() is None:
            conn.execute(
                sa.text("""
                    INSERT INTO company_mappings (plane_project_name, display_name_ru, display_name_en, is_active)
                    VALUES (:plane_name, :ru_name, :en_name, true)
                """),
                {"plane_name": plane_name, "ru_name": ru_name, "en_name": en_name}
            )


def downgrade() -> None:
    # Remove added columns
    op.drop_column('plane_telegram_mappings', 'group_handle')
    op.drop_column('plane_telegram_mappings', 'short_name')

    # Note: We don't remove seeded companies as they may have been modified
