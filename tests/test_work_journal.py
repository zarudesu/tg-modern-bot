"""
Тестовый файл для проверки функциональности модуля журнала работ
"""
import asyncio
import sys
from datetime import date, timedelta

# Add project path for module imports
sys.path.append('/path/to/your/project')

from app.database.database import get_async_session, init_db
from app.services.work_journal_service import WorkJournalService, init_default_data
from app.services.n8n_integration_service import N8nIntegrationService
from app.utils.work_journal_constants import WorkJournalState


async def test_work_journal():
    """Тестирование основных функций модуля журнала работ"""
    print("🧪 Начинаем тестирование модуля журнала работ...")
    
    try:
        # Инициализация базы данных
        print("📊 Инициализация базы данных...")
        await init_db()
        
        async for session in get_async_session():
            # Инициализация дефолтных данных
            print("📝 Инициализация дефолтных данных...")
            await init_default_data(session)
            
            # Создание сервиса
            service = WorkJournalService(session)
            
            # Тест 1: Получение компаний
            print("\n1️⃣ Тестирование получения компаний...")
            companies = await service.get_companies()
            print(f"   ✅ Получено компаний: {len(companies)}")
            print(f"   📋 Список: {', '.join(companies[:5])}...")
            
            # Тест 2: Получение исполнителей
            print("\n2️⃣ Тестирование получения исполнителей...")
            workers = await service.get_workers()
            print(f"   ✅ Получено исполнителей: {len(workers)}")
            print(f"   👥 Список: {', '.join(workers)}")
            
            # Тест 3: Создание состояния пользователя
            print("\n3️⃣ Тестирование состояний пользователя...")
            test_user_id = 123456789
            
            state = await service.set_user_state(
                test_user_id,
                WorkJournalState.SELECTING_COMPANY,
                draft_date=date.today(),
                draft_company="Тестовая компания"
            )
            print(f"   ✅ Создано состояние: {state.current_state}")
            
            # Получение состояния
            retrieved_state = await service.get_user_state(test_user_id)
            print(f"   ✅ Получено состояние: {retrieved_state.current_state}")
            print(f"   📅 Дата: {retrieved_state.draft_date}")
            print(f"   🏢 Компания: {retrieved_state.draft_company}")
            
            # Тест 4: Создание записи в журнале
            print("\n4️⃣ Тестирование создания записи...")
            entry = await service.create_work_entry(
                telegram_user_id=test_user_id,
                user_email="test@example.com",
                work_date=date.today(),
                company="Тест Компания",
                work_duration="30 мин",
                work_description="Тестовое описание работ для проверки функциональности",
                is_travel=True,
                worker_name="Тестовый исполнитель"
            )
            print(f"   ✅ Создана запись ID: {entry.id}")
            print(f"   📅 Дата: {entry.work_date}")
            print(f"   🏢 Компания: {entry.company}")
            print(f"   ⏱ Длительность: {entry.work_duration}")
            
            # Тест 5: Получение записей
            print("\n5️⃣ Тестирование получения записей...")
            entries = await service.get_work_entries(
                telegram_user_id=test_user_id,
                limit=5
            )
            print(f"   ✅ Получено записей: {len(entries)}")
            
            # Тест 6: Статистика
            print("\n6️⃣ Тестирование статистики...")
            stats = await service.get_statistics(
                telegram_user_id=test_user_id
            )
            print(f"   ✅ Общее количество записей: {stats['total_entries']}")
            print(f"   🚗 Выездов: {stats['travel_count']}")
            print(f"   💻 Удаленно: {stats['remote_count']}")
            
            # Тест 7: Очистка состояния
            print("\n7️⃣ Тестирование очистки состояния...")
            cleared = await service.clear_user_state(test_user_id)
            print(f"   ✅ Состояние очищено: {cleared}")
            
            # Тест 8: n8n интеграция (тест подключения)
            print("\n8️⃣ Тестирование n8n интеграции...")
            n8n_service = N8nIntegrationService()
            
            # Проверяем подключение (если URL не настроен, просто сообщаем об этом)
            if hasattr(n8n_service, 'webhook_url') and n8n_service.webhook_url:
                success, message = await n8n_service.test_connection()
                print(f"   🔌 Тест подключения: {'✅' if success else '❌'}")
                print(f"   📝 Сообщение: {message}")
            else:
                print("   ⚠️ n8n webhook URL не настроен - пропускаем тест подключения")
            
            print("\n🎉 Все тесты завершены успешно!")
            
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()


async def test_formatters():
    """Тестирование форматтеров"""
    print("\n🎨 Тестирование форматтеров...")
    
    try:
        from app.utils.work_journal_formatters import (
            escape_markdown_v2,
            format_date_for_display,
            format_help_message
        )
        
        # Тест экранирования
        test_text = "Тест с [символами] (для) экранирования!"
        escaped = escape_markdown_v2(test_text)
        print(f"   ✅ Экранирование: {escaped}")
        
        # Тест форматирования даты
        today = date.today()
        yesterday = today - timedelta(days=1)
        
        today_formatted = format_date_for_display(today)
        yesterday_formatted = format_date_for_display(yesterday)
        
        print(f"   ✅ Сегодня: {today_formatted}")
        print(f"   ✅ Вчера: {yesterday_formatted}")
        
        # Тест справки
        help_text = format_help_message()
        print(f"   ✅ Справка сгенерирована: {len(help_text)} символов")
        
    except Exception as e:
        print(f"❌ Ошибка при тестировании форматтеров: {e}")


async def test_keyboards():
    """Тестирование клавиатур"""
    print("\n⌨️ Тестирование клавиатур...")
    
    try:
        from app.utils.work_journal_keyboards import (
            create_date_selection_keyboard,
            create_company_selection_keyboard,
            create_duration_selection_keyboard,
            parse_callback_data,
            build_callback_data
        )
        from app.utils.work_journal_constants import CallbackAction
        
        # Тест создания callback данных
        callback_data = build_callback_data(CallbackAction.SELECT_COMPANY, "Тест Компания")
        print(f"   ✅ Callback данные: {callback_data}")
        
        # Тест парсинга callback данных
        action, data = parse_callback_data(callback_data)
        print(f"   ✅ Распарсено - действие: {action}, данные: {data}")
        
        # Тест создания клавиатур
        date_keyboard = create_date_selection_keyboard()
        print(f"   ✅ Клавиатура выбора даты создана: {len(date_keyboard.inline_keyboard)} рядов")
        
        companies = ["Компания 1", "Компания 2", "Компания 3"]
        company_keyboard = create_company_selection_keyboard(companies)
        print(f"   ✅ Клавиатура компаний создана: {len(company_keyboard.inline_keyboard)} рядов")
        
        duration_keyboard = create_duration_selection_keyboard()
        print(f"   ✅ Клавиатура длительности создана: {len(duration_keyboard.inline_keyboard)} рядов")
        
    except Exception as e:
        print(f"❌ Ошибка при тестировании клавиатур: {e}")


async def main():
    """Основная функция тестирования"""
    print("🚀 Запуск тестов модуля журнала работ")
    print("=" * 50)
    
    await test_work_journal()
    await test_formatters()
    await test_keyboards()
    
    print("\n" + "=" * 50)
    print("✅ Тестирование завершено!")


if __name__ == "__main__":
    asyncio.run(main())
