"""Add plane_telegram_mappings and company_mappings tables

Revision ID: 007_plane_mappings
Revises: 006_add_project_identifier
Create Date: 2026-01-20

Replaces hardcoded PLANE_TO_TELEGRAM_MAP and COMPANY_MAPPING
in task_reports_service.py with database tables.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '007_plane_mappings'
down_revision = '006_add_project_identifier'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create plane_telegram_mappings table
    op.create_table(
        'plane_telegram_mappings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('lookup_key', sa.String(255), nullable=False),
        sa.Column('telegram_id', sa.BigInteger(), nullable=False),
        sa.Column('telegram_username', sa.String(255), nullable=True),
        sa.Column('display_name', sa.String(255), nullable=True),
        sa.Column('plane_email', sa.String(255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('created_by', sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('lookup_key')
    )
    op.create_index('idx_plane_mapping_telegram_id', 'plane_telegram_mappings', ['telegram_id'])
    op.create_index('idx_plane_mapping_lookup', 'plane_telegram_mappings', ['lookup_key'])
    op.create_index('idx_plane_mapping_active', 'plane_telegram_mappings', ['is_active'])

    # Create company_mappings table
    op.create_table(
        'company_mappings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('plane_project_name', sa.String(255), nullable=False),
        sa.Column('plane_project_id', sa.String(255), nullable=True),
        sa.Column('display_name_ru', sa.String(255), nullable=False),
        sa.Column('display_name_en', sa.String(255), nullable=True),
        sa.Column('client_chat_id', sa.BigInteger(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('plane_project_name')
    )
    op.create_index('idx_company_mapping_project', 'company_mappings', ['plane_project_name'])
    op.create_index('idx_company_mapping_active', 'company_mappings', ['is_active'])

    # Insert initial data from hardcoded mappings
    _insert_initial_plane_mappings()
    _insert_initial_company_mappings()


def _insert_initial_plane_mappings():
    """Insert initial Plane→Telegram mappings from hardcoded values"""
    mappings = [
        # Zardes / Костя Макейкин
        ('Zardes', 28795547, 'zardes', 'Константин Макейкин', 'zarudesu@gmail.com'),
        ('Костя', 28795547, 'zardes', 'Константин Макейкин', None),
        ('Константин Макейкин', 28795547, 'zardes', 'Константин Макейкин', None),
        ('Костя Макейкин', 28795547, 'zardes', 'Константин Макейкин', None),
        ('zarudesu@gmail.com', 28795547, 'zardes', 'Константин Макейкин', 'zarudesu@gmail.com'),

        # Дима Гусев
        ('Дима Гусев', 132228544, 'dima_gusev', 'Дмитрий Гусев', 'gusev@hhivp.com'),
        ('Дима', 132228544, 'dima_gusev', 'Дмитрий Гусев', None),
        ('D. Gusev', 132228544, 'dima_gusev', 'Дмитрий Гусев', None),
        ('Дмитрий', 132228544, 'dima_gusev', 'Дмитрий Гусев', None),
        ('Дмитрий Гусев', 132228544, 'dima_gusev', 'Дмитрий Гусев', None),
        ('gen.director@hhivp.com', 132228544, 'dima_gusev', 'Дмитрий Гусев', 'gen.director@hhivp.com'),
        ('gusev@hhivp.com', 132228544, 'dima_gusev', 'Дмитрий Гусев', 'gusev@hhivp.com'),

        # Тимофей Батырев
        ('Тимофей Батырев', 56994156, 'timofey_batyrev', 'Тимофей Батырев', 'tim.4ud@gmail.com'),
        ('Тимофей', 56994156, 'timofey_batyrev', 'Тимофей Батырев', None),
        ('tim.4ud@gmail.com', 56994156, 'timofey_batyrev', 'Тимофей Батырев', 'tim.4ud@gmail.com'),
    ]

    table = sa.table(
        'plane_telegram_mappings',
        sa.column('lookup_key', sa.String),
        sa.column('telegram_id', sa.BigInteger),
        sa.column('telegram_username', sa.String),
        sa.column('display_name', sa.String),
        sa.column('plane_email', sa.String),
        sa.column('created_by', sa.String),
    )

    for lookup_key, tg_id, tg_username, display_name, email in mappings:
        op.execute(
            table.insert().values(
                lookup_key=lookup_key,
                telegram_id=tg_id,
                telegram_username=tg_username,
                display_name=display_name,
                plane_email=email,
                created_by='migration_006'
            )
        )


def _insert_initial_company_mappings():
    """Insert initial company mappings from hardcoded values"""
    companies = [
        ('HHIVP', 'HHIVP'),
        ('HARZL', 'ХАРЗЛ'),
        ('DELTA', 'ДЕЛЬТА'),
        ('INFOTECS', 'Инфотекс'),
        ('GAZPROM', 'Газпром'),
        ('ROGA', 'Рога и Копыта'),
        ('INTERNAL', 'Внутренние задачи'),
    ]

    table = sa.table(
        'company_mappings',
        sa.column('plane_project_name', sa.String),
        sa.column('display_name_ru', sa.String),
    )

    for plane_name, ru_name in companies:
        op.execute(
            table.insert().values(
                plane_project_name=plane_name,
                display_name_ru=ru_name
            )
        )


def downgrade() -> None:
    op.drop_index('idx_company_mapping_active', table_name='company_mappings')
    op.drop_index('idx_company_mapping_project', table_name='company_mappings')
    op.drop_table('company_mappings')

    op.drop_index('idx_plane_mapping_active', table_name='plane_telegram_mappings')
    op.drop_index('idx_plane_mapping_lookup', table_name='plane_telegram_mappings')
    op.drop_index('idx_plane_mapping_telegram_id', table_name='plane_telegram_mappings')
    op.drop_table('plane_telegram_mappings')
