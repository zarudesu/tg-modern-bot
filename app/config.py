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
    admin_user_id: int
    
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
    
    @field_validator('telegram_token')
    @classmethod
    def validate_telegram_token(cls, v):
        if not v or len(v) < 10:
            raise ValueError('Invalid Telegram token')
        return v
    
    @field_validator('database_url')
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
ADMIN_USER_ID = settings.admin_user_id
DATABASE_URL = settings.database_url
REDIS_URL = settings.redis_url
# NETBOX_URL = settings.netbox_url
# NETBOX_TOKEN = settings.netbox_token
LOG_LEVEL = settings.log_level