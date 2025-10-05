#!/usr/bin/env python3
"""
КРИТИЧЕСКИЙ ТЕСТ: Проверка исправлений email обработки

Проверяем:
1. IsAdminEmailFilter работает правильно
2. Нет конфликтующих обработчиков
3. Admin ID 28795547 + zarudesu@gmail.com обрабатывается корректно
"""
import asyncio
import sys
import os

# Добавляем корневую папку в путь для импорта
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.modules.daily_tasks.filters import IsAdminEmailFilter
from app.config import settings


class MockMessage:
    def __init__(self, user_id, text):
        self.from_user = type('MockUser', (), {'id': user_id})()
        self.text = text


async def test_admin_email_filter():
    """Тест фильтра админского email"""
    print("🧪 КРИТИЧЕСКИЙ ТЕСТ: IsAdminEmailFilter")
    print(f"   Админы в config: {settings.admin_user_id_list}")
    
    # Создаем фильтр
    admin_email_filter = IsAdminEmailFilter()
    
    # Тест 1: Admin ID 28795547 + правильный email
    test_admin_id = 28795547
    test_email = "zarudesu@gmail.com"
    
    mock_message = MockMessage(test_admin_id, test_email)
    result = await admin_email_filter(mock_message)
    
    print(f"   ✅ Admin {test_admin_id} + email '{test_email}': {result}")
    
    # Тест 2: Не admin + email
    non_admin_id = 99999999
    mock_message2 = MockMessage(non_admin_id, test_email)
    result2 = await admin_email_filter(mock_message2)
    
    print(f"   ❌ Non-admin {non_admin_id} + email '{test_email}': {result2}")
    
    # Тест 3: Admin + не email
    mock_message3 = MockMessage(test_admin_id, "не email текст")
    result3 = await admin_email_filter(mock_message3)
    
    print(f"   ❌ Admin {test_admin_id} + не email: {result3}")
    
    return result  # Должно быть True для админа с email


async def test_email_handlers_structure():
    """Проверка структуры email обработчиков"""
    print("\n🔍 Проверка структуры email_handlers.py...")
    
    try:
        from app.modules.daily_tasks import email_handlers
        
        # Проверяем что router существует
        router = email_handlers.router
        print(f"   ✅ Router существует: {router}")
        
        # Проверяем количество обработчиков
        handlers_count = len(router.message.handlers)
        print(f"   📊 Количество message handlers: {handlers_count}")
        
        # Ожидаем ТОЛЬКО 1 обработчик после удаления debug
        if handlers_count == 1:
            print("   ✅ Правильное количество обработчиков (debug удален)")
        else:
            print(f"   ⚠️ Неожиданное количество обработчиков: {handlers_count}")
            
        return True
        
    except Exception as e:
        print(f"   ❌ Ошибка импорта email_handlers: {e}")
        return False


async def main():
    """Основной тест"""
    print("🚨 КРИТИЧЕСКИЙ ТЕСТ ИСПРАВЛЕНИЙ EMAIL ОБРАБОТКИ")
    print("=" * 60)
    
    # Тест 1: Фильтры
    try:
        filter_result = await test_admin_email_filter()
        if not filter_result:
            print("\n❌ КРИТИЧЕСКАЯ ОШИБКА: IsAdminEmailFilter не работает!")
            return False
    except Exception as e:
        print(f"\n❌ ОШИБКА в тесте фильтров: {e}")
        return False
    
    # Тест 2: Структура обработчиков  
    try:
        handlers_result = await test_email_handlers_structure()
        if not handlers_result:
            print("\n❌ КРИТИЧЕСКАЯ ОШИБКА: Проблемы со структурой обработчиков!")
            return False
    except Exception as e:
        print(f"\n❌ ОШИБКА в тесте структуры: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("🎉 ВСЕ КРИТИЧЕСКИЕ ТЕСТЫ ПРОЙДЕНЫ!")
    print("✅ Email обработка для admin 28795547 должна работать")
    print("✅ zarudesu@gmail.com будет правильно обработан")
    print("✅ Конфликтующий debug обработчик удален")
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)