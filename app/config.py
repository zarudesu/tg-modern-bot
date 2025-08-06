"""
Конфигурация приложения
"""
import os
from typing import Optional, List
from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Настройки приложения"""
    
    # Telegram Bot
    telegram_token: str
    telegram_api_id: int
    telegram_api_hash: str
    admin_user_ids: str  # Строка с ID админов через запятую
    
    # Database
    database_url: str
    redis_url: str
    
    # API Integrations (optional)
    # netbox_url: Optional[str] = None
    # netbox_token: Optional[str] = None
    vaultwarden_url: Optional[str] = None
    outline_url: Optional[str] = None
    zammad_url: Optional[str] = None
    zammad_token: Optional[str] = None
    
    # n8n Integration (for work journal)
    n8n_webhook_url: Optional[str] = None
    n8n_webhook_secret: Optional[str] = None
    
    # Group Notifications
    work_journal_group_chat_id: Optional[int] = None
    google_sheets_url: Optional[str] = None
    
    # Google Sheets Configuration (used by n8n)
    google_sheets_id: Optional[str] = None
    google_sheets_credentials_json: Optional[str] = None  # JSON строка с credentials
    google_sheets_credentials_file: Optional[str] = None  # Путь к файлу с credentials
    
    # Plane Integration
    plane_chat_id: Optional[int] = None
    plane_topic_id: Optional[int] = None
    plane_webhook_secret: Optional[str] = None
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "json"
    max_log_size: str = "100MB"
    log_retention: str = "30d"
    
    # Bot Settings
    rate_limit_default: str = "10/minute"
    rate_limit_search: str = "30/minute"
    rate_limit_admin: str = "100/minute"
    
    # Security
    allowed_chat_types: List[str] = ["private", "group", "supergroup"]
    max_search_results: int = 20
    session_timeout: int = 3600  # 1 hour
    
    @field_validator('admin_user_ids')
    @classmethod
    def validate_admin_user_ids(cls, v):
        if not v or not v.strip():
            raise ValueError('At least one admin user ID is required')
        # Проверяем, что все ID являются числами
        try:
            ids = [int(id.strip()) for id in v.split(',') if id.strip()]
            if not ids:
                raise ValueError('At least one valid admin user ID is required')
            return v
        except ValueError:
            raise ValueError('Admin user IDs must be comma-separated integers')
    
    @property
    def admin_user_id_list(self) -> List[int]:
        """Получить список ID админов как список чисел"""
        return [int(id.strip()) for id in self.admin_user_ids.split(',') if id.strip()]
    
    def is_admin(self, user_id: int) -> bool:
        """Проверить, является ли пользователь администратором"""
        return user_id in self.admin_user_id_list
    
    @field_validator('telegram_token')
    @classmethod
    def validate_telegram_token(cls, v):
        if not v or len(v) < 10:
            raise ValueError('Invalid Telegram token')
        return v
    @classmethod
    def validate_database_url(cls, v):
        if not v.startswith(('postgresql://', 'postgresql+asyncpg://')):
            raise ValueError('Invalid database URL')
        return v
    
    # @field_validator('netbox_url')
    # @classmethod
    # def validate_netbox_url(cls, v):
    #     if not v.startswith(('http://', 'https://')):
    #         raise ValueError('Invalid NetBox URL')
    #     return v.rstrip('/')
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Глобальный экземпляр настроек
settings = Settings()

# Константы для удобства
TELEGRAM_TOKEN = settings.telegram_token
ADMIN_USER_IDS = settings.admin_user_id_list
DATABASE_URL = settings.database_url
REDIS_URL = settings.redis_url
# NETBOX_URL = settings.netbox_url
# NETBOX_TOKEN = settings.netbox_token
LOG_LEVEL = settings.log_level