#!/usr/bin/env python3
"""
Тест n8n интеграции - проверка отправки данных
"""
import asyncio
import sys
import os
from datetime import date
import json

# Добавляем корневую директорию проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.n8n_integration_service import N8nIntegrationService
from app.database.work_journal_models import WorkJournalEntry


def create_test_entry():
    """Создать тестовую запись"""
    from datetime import datetime
    
    entry = WorkJournalEntry()
    entry.id = 999
    entry.telegram_user_id = 123456789
    entry.user_email = "zardes@hhivp.com"
    entry.work_date = date.today()
    entry.company = "Тестовая компания"
    entry.work_duration = "1 час 30 мин"
    entry.work_description = "Тестирование n8n интеграции с новым парсером времени"
    entry.is_travel = True
    entry.worker_names = json.dumps(["Тимофей Батырев", "Дмитрий Гусев"], ensure_ascii=False)
    entry.created_by_user_id = 123456789
    entry.created_by_name = "@zardes"
    entry.created_at = datetime.now()  # Добавляем created_at
    entry.n8n_sync_attempts = 0
    
    return entry


async def test_n8n_integration():
    """Тест интеграции с n8n"""
    print("🧪 Тестирование n8n интеграции")
    print("=" * 50)
    
    # Создаем сервис
    n8n_service = N8nIntegrationService()
    
    if not n8n_service.webhook_url:
        print("❌ N8n webhook URL не настроен в .env файле")
        return False
    
    print(f"🔗 Webhook URL: {n8n_service.webhook_url}")
    
    # Тест соединения
    print("\n1️⃣ Тестирование соединения...")
    connection_ok, connection_msg = await n8n_service.test_connection()
    
    if connection_ok:
        print(f"✅ Соединение: {connection_msg}")
    else:
        print(f"❌ Соединение: {connection_msg}")
        return False
    
    # Тест отправки данных
    print("\n2️⃣ Тестирование отправки записи...")
    
    test_entry = create_test_entry()
    user_data = {
        "first_name": "Константин",
        "username": "zardes"
    }
    
    # Показать данные, которые будут отправлены
    webhook_data = n8n_service._prepare_webhook_data(test_entry, user_data)
    
    print("📤 Данные для отправки:")
    print(json.dumps(webhook_data, indent=2, ensure_ascii=False))
    
    # Отправляем
    success, error_msg = await n8n_service.send_work_entry(test_entry, user_data)
    
    if success:
        print("✅ Данные успешно отправлены в n8n!")
        
        # Проверяем ключевые поля
        work_entry = webhook_data["data"]["work_entry"]
        print(f"\n📊 Проверка ключевых полей:")
        print(f"   • duration (число): {work_entry['duration']} минут")
        print(f"   • duration_text (текст): {work_entry['duration_text']}")
        print(f"   • Исполнители: {', '.join(work_entry['workers'])}")
        print(f"   • Выезд: {'Да' if work_entry['is_travel'] else 'Нет'}")
        
    else:
        print(f"❌ Ошибка отправки: {error_msg}")
        return False
    
    print("\n🎉 Все тесты пройдены успешно!")
    return True


if __name__ == "__main__":
    try:
        result = asyncio.run(test_n8n_integration())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n⏹️  Тест прерван пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Ошибка во время теста: {e}")
        sys.exit(1)
