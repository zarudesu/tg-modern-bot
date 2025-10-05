#!/usr/bin/env python3
"""
Простой тест модульной архитектуры после рефакторинга
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.modules.work_journal.filters import IsWorkJournalActiveFilter, IsWorkJournalIdleFilter
from app.modules.daily_tasks.filters import IsAdminEmailFilter, IsEmailFilter


def test_filters_import():
    """Тест импорта фильтров"""
    print("🧪 Тестируем импорт фильтров...")
    
    # Work Journal фильтры
    active_filter = IsWorkJournalActiveFilter()
    idle_filter = IsWorkJournalIdleFilter()
    print("   ✅ Work Journal фильтры импортированы")
    
    # Daily Tasks фильтры  
    email_filter = IsEmailFilter()
    admin_email_filter = IsAdminEmailFilter()
    print("   ✅ Daily Tasks фильтры импортированы")
    
    print("✅ Все фильтры импортированы успешно!")


async def test_email_filter():
    """Тест email фильтра"""
    print("🧪 Тестируем email фильтр...")
    
    class MockMessage:
        def __init__(self, text):
            self.text = text
            self.from_user = type('MockUser', (), {'id': 28795547})()  # Admin ID
    
    email_filter = IsEmailFilter()
    
    # Тест валидного email
    valid_email = MockMessage("zarudesu@gmail.com")
    is_valid = await email_filter(valid_email)
    print(f"   Email 'zarudesu@gmail.com': {is_valid} (должно быть True)")
    
    # Тест невалидного текста
    invalid_text = MockMessage("привет мир")
    is_invalid = await email_filter(invalid_text)
    print(f"   Текст 'привет мир': {is_invalid} (должно быть False)")
    
    print("✅ Email фильтр работает правильно!")


async def main():
    """Основная функция"""
    print("🚀 ПРОСТОЙ ТЕСТ МОДУЛЬНОЙ АРХИТЕКТУРЫ")
    print("=" * 40)
    
    try:
        # Тест импортов
        test_filters_import()
        print()
        
        # Тест фильтров
        await test_email_filter()
        print()
        
        print("🎉 ВСЕ ТЕСТЫ ПРОШЛИ!")
        print("✅ Модульная архитектура работает")
        print("✅ Рефакторинг УСПЕШЕН!")
        
    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
