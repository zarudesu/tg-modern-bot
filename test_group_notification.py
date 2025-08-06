#!/usr/bin/env python3
"""
Тест отправки уведомления в групповой чат
"""
import asyncio
import sys
import os
from datetime import date, datetime
import json

# Добавляем корневую директорию проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram import Bot
from app.config import settings


async def test_group_notification():
    """Тест отправки уведомления в группу"""
    print("🧪 Тестирование отправки в групповой чат")
    print("=" * 50)
    
    # Проверяем настройки
    if not settings.work_journal_group_chat_id:
        print("❌ WORK_JOURNAL_GROUP_CHAT_ID не настроен в .env")
        return False
    
    print(f"📱 Group Chat ID: {settings.work_journal_group_chat_id}")
    print(f"📊 Google Sheets URL: {settings.google_sheets_url}")
    
    # Создаем тестовое сообщение
    test_message = (
        "📋 Новая запись в журнале работ\n"
        "👤 Добавил: @zardes\n\n"
        "📅 2025-08-05\n"
        "🏢 Тестовая компания\n"
        "⏰ 2 часа\n"
        "📝 Тестирование уведомлений в групповой чат\n"
        "👥 Константин Макейкин\n"
        "🚗 Выезд: Да\n\n"
        f'📊 <a href="{settings.google_sheets_url}">Google Sheets</a>\n\n'
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    
    print("\n📤 Отправляем тестовое сообщение:")
    print(test_message)
    
    try:
        bot = Bot(token=settings.telegram_token)
        
        # Отправляем сообщение
        message = await bot.send_message(
            chat_id=settings.work_journal_group_chat_id,
            text=test_message,
            parse_mode="HTML",  # Используем HTML для ссылок
            disable_web_page_preview=True
        )
        
        print(f"\n✅ Сообщение успешно отправлено!")
        print(f"   Message ID: {message.message_id}")
        print(f"   Chat ID: {message.chat.id}")
        print(f"   Chat Title: {message.chat.title}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Ошибка отправки: {e}")
        return False


if __name__ == "__main__":
    try:
        success = asyncio.run(test_group_notification())
        if success:
            print("\n🎉 Тест прошел успешно!")
            print("   Теперь при создании записи в боте будут отправляться уведомления в группу")
        else:
            print("\n💥 Тест не прошел")
        
    except Exception as e:
        print(f"\n💥 Ошибка: {e}")
