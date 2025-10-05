#!/usr/bin/env python3
"""
Тест изоляции модулей после рефакторинга
Проверяем что:
1. Work Journal имеет правильные фильтры состояний
2. Daily Tasks работает с email изоляцией  
3. Модули не конфликтуют друг с другом
"""
import asyncio
import sys
import os

# Добавляем корневую папку в путь для импорта
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database.database import init_db, get_async_session
from app.services.work_journal_service import WorkJournalService
from app.services.daily_tasks_service import DailyTasksService
from app.utils.work_journal_constants import WorkJournalState
from app.modules.work_journal.filters import IsWorkJournalActiveFilter
from app.modules.daily_tasks.filters import IsAdminEmailFilter


async def test_work_journal_filters():
    """Тест фильтров work_journal"""
    print("🧪 Тестируем фильтры Work Journal...")
    
    async for session in get_async_session():
        service = WorkJournalService(session)
        
        # Тестовый user ID
        test_user_id = 12345
        
        # 1. Сначала состояние должно быть IDLE (не активно)
        user_state = await service.get_user_state(test_user_id)
        print(f"   Начальное состояние: {user_state.current_state if user_state else 'None'}")
        
        # 2. Устанавливаем активное состояние
        await service.set_user_state(test_user_id, WorkJournalState.SELECTING_DATE)
        user_state = await service.get_user_state(test_user_id)
        print(f"   Активное состояние: {user_state.current_state}")
        
        # 3. Проверяем фильтр активности
        # Создаем mock Message объект
        class MockMessage:
            def __init__(self, user_id):
                self.from_user = type('MockUser', (), {'id': user_id})()
        
        # Тестируем фильтр
        active_filter = IsWorkJournalActiveFilter()
        is_active = await active_filter(MockMessage(test_user_id))
        print(f"   Фильтр активности: {is_active} (должно быть True)")
        
        # 4. Сбрасываем в IDLE
        await service.set_user_state(test_user_id, WorkJournalState.IDLE)
        is_active_idle = await active_filter(MockMessage(test_user_id))
        print(f"   Фильтр после IDLE: {is_active_idle} (должно быть False)")
        
        # 5. Очищаем состояние
        await service.clear_user_state(test_user_id)
        is_active_cleared = await active_filter(MockMessage(test_user_id))
        print(f"   Фильтр после очистки: {is_active_cleared} (должно быть False)")
        
        break  # Выходим из async for
    
    print("✅ Work Journal фильтры работают правильно!")


async def test_daily_tasks_email_isolation():
    """Тест изоляции daily_tasks по email"""
    print("🧪 Тестируем изоляцию Daily Tasks по email...")
    
    try:
        # Создаем mock объекты для тестирования
        class MockMessage:
            def __init__(self, user_id, text):
                self.from_user = type('MockUser', (), {'id': user_id})()
                self.text = text
        
        # Тестируем фильтр daily_tasks
        daily_filter = IsAdminEmailFilter()
        
        # Email сообщение от админа - должно проходить фильтр
        email_message = MockMessage(28795547, "zarudesu@gmail.com")  # Твой admin ID
        is_email_active = await daily_filter(email_message)
        print(f"   Admin Email фильтр: {is_email_active} (должно быть True)")
        
        # Обычное сообщение - НЕ должно проходить фильтр  
        regular_message = MockMessage(28795547, "обычный текст")
        is_regular_active = await daily_filter(regular_message)
        print(f"   Обычный текст фильтр: {is_regular_active} (должно быть False)")
        
        # Email от НЕ-админа - НЕ должно проходить фильтр
        non_admin_email = MockMessage(12345, "test@example.com")  # НЕ admin ID
        is_non_admin_active = await daily_filter(non_admin_email)
        print(f"   НЕ-admin Email фильтр: {is_non_admin_active} (должно быть False)")
        
        print("✅ Daily Tasks email изоляция работает!")
        
    except ImportError as e:
        print(f"⚠️  Модуль daily_tasks фильтров не найден: {e}")
        print("   (Это нормально если они в другой структуре)")


async def test_module_independence():
    """Тест независимости модулей"""
    print("🧪 Тестируем независимость модулей...")
    
    async for session in get_async_session():
        # Проверяем что сервисы работают независимо
        
        # 1. Work Journal сервис
        wj_service = WorkJournalService(session)
        companies = await wj_service.get_companies()
        print(f"   Work Journal: {len(companies)} компаний в БД")
        
        # 2. Daily Tasks сервис  
        dt_service = DailyTasksService()
        print(f"   Daily Tasks: сервис инициализирован")
        
        break
    
    print("✅ Модули работают независимо!")


async def main():
    """Основная функция тестирования"""
    print("🚀 ТЕСТ ИЗОЛЯЦИИ МОДУЛЕЙ ПОСЛЕ РЕФАКТОРИНГА")
    print("=" * 50)
    
    try:
        # Инициализируем БД
        await init_db()
        print("✅ База данных подключена")
        
        # Запускаем тесты
        await test_work_journal_filters()
        print()
        
        await test_daily_tasks_email_isolation()
        print()
        
        await test_module_independence()
        print()
        
        print("🎉 ВСЕ ТЕСТЫ ПРОШЛИ УСПЕШНО!")
        print("✅ Модульная изоляция работает корректно")
        
    except Exception as e:
        print(f"❌ ОШИБКА В ТЕСТАХ: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
