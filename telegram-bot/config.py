import os
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    """Настройки приложения"""
    
    # Telegram Bot
    BOT_TOKEN: str = Field(..., description="Токен Telegram бота")
    
    # База данных
    DATABASE_URL: str = Field(..., description="URL подключения к PostgreSQL")
    
    # Redis
    REDIS_URL: str = Field(..., description="URL подключения к Redis")
    
    # NetBox
    NETBOX_URL: str = Field(..., description="URL NetBox")
    NETBOX_TOKEN: str = Field(default="", description="API токен NetBox")
    
    # Vaultwarden
    VAULTWARDEN_URL: str = Field(..., description="URL Vaultwarden")
    
    # BookStack
    BOOKSTACK_URL: str = Field(..., description="URL BookStack")
    BOOKSTACK_TOKEN: str = Field(default="", description="API токен BookStack")
    
    # Безопасность
    ALLOWED_USERS: list[int] = Field(default=[], description="ID разрешенных пользователей")
    ADMIN_USERS: list[int] = Field(default=[], description="ID администраторов")
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# Создаем экземпляр настроек
settings = Settings()
