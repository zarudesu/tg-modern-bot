"""
Система логирования для бота
"""
import sys
import json
from pathlib import Path
from typing import Dict, Any
from loguru import logger
from ..config import settings


class JSONFormatter:
    """Форматтер для JSON логов"""
    
    def format(self, record: Dict[str, Any]) -> str:
        """Форматирование записи в JSON"""
        log_record = {
            "timestamp": record["time"].isoformat(),
            "level": record["level"].name,
            "module": record["name"],
            "function": record["function"],
            "line": record["line"],
            "message": record["message"],
        }
        
        # Добавляем дополнительные поля если есть
        if "extra" in record:
            log_record.update(record["extra"])
            
        return json.dumps(log_record, ensure_ascii=False)


def setup_logging():
    """Настройка системы логирования"""
    
    # Удаляем стандартный обработчик
    logger.remove()
    
    # Создаем папку для логов
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Обработчик для консоли
    if settings.log_format == "json":
        console_format = JSONFormatter().format
    else:
        console_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        )
    
    logger.add(
        sys.stdout,
        format=console_format,
        level=settings.log_level,
        colorize=True if settings.log_format != "json" else False
    )
    
    # Обработчик для файла (всегда JSON)
    logger.add(
        log_dir / "bot.log",
        format=JSONFormatter().format,
        level="DEBUG",
        rotation=settings.max_log_size,
        retention=settings.log_retention,
        compression="gz",
        encoding="utf-8"
    )
    
    # Отдельный файл для ошибок
    logger.add(
        log_dir / "errors.log",
        format=JSONFormatter().format,
        level="ERROR",
        rotation="10 MB",
        retention="60 days",
        compression="gz",
        encoding="utf-8"
    )
    
    return logger


# Инициализация логгера
bot_logger = setup_logging()


def log_api_request(service: str, endpoint: str, method: str, 
                   user_id: int = None, execution_time: float = None):
    """Логирование API запросов"""
    bot_logger.info(
        "API request",
        extra={
            "event_type": "api_request",
            "service": service,
            "endpoint": endpoint,
            "method": method,
            "user_id": user_id,
            "execution_time": execution_time
        }
    )


def log_user_action(user_id: int, action: str, details: Dict[str, Any] = None):
    """Логирование действий пользователей"""
    extra_data = {
        "event_type": "user_action",
        "user_id": user_id,
        "action": action
    }
    
    if details:
        extra_data.update(details)
    
    bot_logger.info(f"User action: {action}", extra=extra_data)


def log_error(error: Exception, context: Dict[str, Any] = None):
    """Логирование ошибок"""
    extra_data = {
        "event_type": "error",
        "error_type": type(error).__name__,
        "error_message": str(error)
    }
    
    if context:
        extra_data.update(context)
    
    bot_logger.error(f"Error occurred: {error}", extra=extra_data)