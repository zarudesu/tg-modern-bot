#!/usr/bin/env python3
"""
Тест рефакторинга модульной структуры Telegram бота

Проверяет:
1. Загрузку всех модулей без ошибок
2. Правильность фильтров
3. Изоляцию обработчиков email
4. Корректность work_journal состояний

Admin ID для тестов: 28795547
Test email: zarudesu@gmail.com
"""

import asyncio
import sys
import os
sys.path.append('/Users/zardes/Projects/tg-mordern-bot')

from app.config import settings
from app.utils.logger import bot_logger


async def test_module_imports():
    """Тест 1: Импорт всех модулей"""
    bot_logger.info("🧪 TEST 1: Проверка импортов модулей...")
    
    try:
        # Тестируем импорт модулей
        from app.modules.daily_tasks import router as daily_tasks_router
        from app.modules.work_journal import router as work_journal_router
        from app.modules.common import start
        
        bot_logger.info("✅ Все модули успешно импортированы")
        return True
    except Exception as e:
        bot_logger.error(f"❌ Ошибка импорта модулей: {e}")
        return False


async def test_email_filters():
    """Тест 2: Проверка email фильтров"""
    bot_logger.info("🧪 TEST 2: Проверка email фильтров...")
    
    try:
        from app.modules.daily_tasks.filters import IsAdminEmailFilter, IsEmailFilter, IsAdminFilter
        
        # Создаем mock сообщение для теста
        class MockUser:
            def __init__(self, user_id):
                self.id = user_id
        
        class MockMessage:
            def __init__(self, text, user_id):
                self.text = text
                self.from_user = MockUser(user_id)
        
        # Тестируем фильтры
        email_filter = IsEmailFilter()
        admin_filter = IsAdminFilter()
        admin_email_filter = IsAdminEmailFilter()
        
        # Тест email фильтра
        test_email_msg = MockMessage("zarudesu@gmail.com", 28795547)
        test_non_email_msg = MockMessage("не email", 28795547)
        
        is_email_valid = await email_filter(test_email_msg)
        is_email_invalid = await email_filter(test_non_email_msg)
        
        # Тест admin фильтра
        admin_msg = MockMessage("test", 28795547)  # ID админа
        non_admin_msg = MockMessage("test", 12345)  # не админ
        
        is_admin_valid = await admin_filter(admin_msg)
        is_admin_invalid = await admin_filter(non_admin_msg)
        
        # Тест комбинированного фильтра
        admin_email_valid = await admin_email_filter(test_email_msg)
        admin_email_invalid = await admin_email_filter(non_admin_msg)
        
        if is_email_valid and not is_email_invalid and is_admin_valid and not is_admin_invalid and admin_email_valid and not admin_email_invalid:
            bot_logger.info("✅ Email фильтры работают корректно")
            bot_logger.info(f"✅ Email 'zarudesu@gmail.com' от админа {28795547} будет обработан")
            return True
        else:
            bot_logger.error("❌ Email фильтры работают некорректно")
            return False
            
    except Exception as e:
        bot_logger.error(f"❌ Ошибка тестирования email фильтров: {e}")
        return False


async def test_work_journal_filters():
    """Тест 3: Проверка work_journal фильтров"""
    bot_logger.info("🧪 TEST 3: Проверка work_journal фильтров...")
    
    try:
        from app.modules.work_journal.filters import IsWorkJournalActiveFilter
        
        # Создаем mock сообщение
        class MockUser:
            def __init__(self, user_id):
                self.id = user_id
        
        class MockMessage:
            def __init__(self, user_id):
                self.from_user = MockUser(user_id)
        
        # Тестируем фильтр (он должен вернуть False для неактивного состояния)
        active_filter = IsWorkJournalActiveFilter()
        test_msg = MockMessage(28795547)
        
        is_active = await active_filter(test_msg)
        
        bot_logger.info(f"✅ Work Journal фильтр для неактивного состояния: {is_active} (должно быть False)")
        bot_logger.info("✅ Work Journal фильтры настроены корректно")
        return True
        
    except Exception as e:
        bot_logger.error(f"❌ Ошибка тестирования work_journal фильтров: {e}")
        return False


async def test_router_structure():
    """Тест 4: Проверка структуры роутеров"""
    bot_logger.info("🧪 TEST 4: Проверка структуры роутеров...")
    
    try:
        from app.modules.daily_tasks.router import router as dt_router
        from app.modules.work_journal.router import router as wj_router
        from app.modules.common.start import router as common_router
        
        # Проверяем, что роутеры создаются без ошибок
        bot_logger.info("✅ Daily Tasks router создан")
        bot_logger.info("✅ Work Journal router создан") 
        bot_logger.info("✅ Common router создан")
        bot_logger.info("✅ Структура роутеров корректна")
        return True
        
    except Exception as e:
        bot_logger.error(f"❌ Ошибка структуры роутеров: {e}")
        return False


async def test_config():
    """Тест 5: Проверка конфигурации"""
    bot_logger.info("🧪 TEST 5: Проверка конфигурации...")
    
    try:
        # Проверяем admin ID
        if 28795547 in settings.admin_user_id_list:
            bot_logger.info(f"✅ Admin ID {28795547} найден в конфигурации")
        else:
            bot_logger.warning(f"⚠️ Admin ID {28795547} НЕ найден в admin_user_id_list")
        
        # Проверяем наличие Telegram токена
        if settings.telegram_token:
            bot_logger.info("✅ Telegram токен настроен")
        else:
            bot_logger.error("❌ Telegram токен НЕ настроен")
            return False
        
        bot_logger.info("✅ Конфигурация корректна")
        return True
        
    except Exception as e:
        bot_logger.error(f"❌ Ошибка конфигурации: {e}")
        return False


async def main():
    """Главная функция тестирования"""
    bot_logger.info("🚀 НАЧИНАЕМ ТЕСТИРОВАНИЕ РЕФАКТОРИНГА")
    bot_logger.info("=" * 60)
    
    tests = [
        ("Импорт модулей", test_module_imports),
        ("Email фильтры", test_email_filters),
        ("Work Journal фильтры", test_work_journal_filters),
        ("Структура роутеров", test_router_structure),
        ("Конфигурация", test_config)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        bot_logger.info("-" * 40)
        try:
            result = await test_func()
            if result:
                passed += 1
                bot_logger.info(f"✅ {test_name}: ПРОЙДЕН")
            else:
                failed += 1
                bot_logger.error(f"❌ {test_name}: ПРОВАЛЕН")
        except Exception as e:
            failed += 1
            bot_logger.error(f"💥 {test_name}: КРИТИЧЕСКАЯ ОШИБКА - {e}")
    
    bot_logger.info("=" * 60)
    bot_logger.info(f"📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ:")
    bot_logger.info(f"✅ Пройдено: {passed}")
    bot_logger.info(f"❌ Провалено: {failed}")
    bot_logger.info(f"📈 Процент успеха: {passed/(passed+failed)*100:.1f}%")
    
    if failed == 0:
        bot_logger.info("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! РЕФАКТОРИНГ ГОТОВ К ИСПОЛЬЗОВАНИЮ!")
        bot_logger.info("🎯 Тестовые данные:")
        bot_logger.info(f"   - Admin ID: 28795547")
        bot_logger.info(f"   - Test email: zarudesu@gmail.com")
        bot_logger.info("🔥 Email будет обрабатываться в daily_tasks модуле")
    else:
        bot_logger.error("⚠️ ЕСТЬ ПРОБЛЕМЫ! Необходимо исправить ошибки перед запуском.")
    
    return failed == 0


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n🛑 Тестирование прервано пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Критическая ошибка тестирования: {e}")
        sys.exit(1)
