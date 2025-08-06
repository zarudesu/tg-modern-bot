#!/usr/bin/env python3
"""
Тест конкретной записи - проверка данных которые отправляются в n8n
"""
import asyncio
import sys
import os
from datetime import date, datetime
import json

# Добавляем корневую директорию проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.n8n_integration_service import N8nIntegrationService
from app.database.work_journal_models import WorkJournalEntry
from app.utils.duration_parser import format_duration_for_n8n


def create_test_entry_with_hours():
    """Создать тестовую запись с часами"""
    entry = WorkJournalEntry()
    entry.id = 999
    entry.telegram_user_id = 123456789
    entry.user_email = "zardes@hhivp.com"
    entry.work_date = date.today()
    entry.company = "Тестовая компания"
    entry.work_duration = "6 часиков"  # Как в логах
    entry.work_description = "Тестирование парсера времени"
    entry.is_travel = True
    entry.worker_names = json.dumps(["Константин Макейкин"], ensure_ascii=False)
    entry.created_by_user_id = 123456789
    entry.created_by_name = "@zardes"
    entry.created_at = datetime.now()
    entry.n8n_sync_attempts = 0
    
    return entry


async def test_duration_parsing():
    """Тест парсинга времени"""
    print("🧪 Тестирование парсинга времени")
    print("=" * 50)
    
    test_cases = [
        "1 час",
        "2 часа", 
        "6 часиков",  # Как в реальной записи
        "30 мин",
        "1.5 часа",
        "90 мин"
    ]
    
    print("Тест парсера:")
    for case in test_cases:
        minutes = format_duration_for_n8n(case)
        print(f"'{case}' -> {minutes} минут")
    
    print("\n" + "=" * 50)
    
    # Создаем n8n сервис
    n8n_service = N8nIntegrationService()
    
    # Создаем тестовую запись
    test_entry = create_test_entry_with_hours()
    user_data = {
        "first_name": "Константин",
        "username": "zardes"
    }
    
    # Подготавливаем данные как в реальном коде
    webhook_data = n8n_service._prepare_webhook_data(test_entry, user_data)
    
    print("📤 Данные, которые отправляются в n8n:")
    work_entry = webhook_data["data"]["work_entry"]
    
    print(f"  • duration (число): {work_entry['duration']} минут")
    print(f"  • duration_text (текст): '{work_entry['duration_text']}'")
    print(f"  • Компания: '{work_entry['company']}'")
    print(f"  • Исполнители: {work_entry['workers']}")
    
    print("\n📋 Полная структура work_entry:")
    print(json.dumps(work_entry, indent=2, ensure_ascii=False))
    
    return work_entry['duration']


if __name__ == "__main__":
    try:
        minutes = asyncio.run(test_duration_parsing())
        
        if minutes == 360:  # 6 часов = 360 минут
            print("\n✅ ТЕПЕРЬ duration СОДЕРЖИТ ЧИСЛО!")
            print(f"   6 часиков -> duration: {minutes} минут (правильно)")
        else:
            print(f"\n❌ ПРОБЛЕМА С ПАРСЕРОМ!")
            print(f"   6 часиков -> duration: {minutes} минут (должно быть 360)")
            
    except Exception as e:
        print(f"\n💥 Ошибка: {e}")
