#!/usr/bin/env python3
"""
Тест интеграции с n8n и Google Sheets
Этот скрипт проверяет работоспособность интеграции
"""

import asyncio
import json
import sys
import aiohttp
from datetime import datetime
from typing import Dict, Any

# Тестовые данные для отправки
TEST_WEBHOOK_DATA = {
    "source": "telegram_bot",
    "event_type": "work_journal_entry",
    "timestamp": datetime.now().isoformat() + "Z",
    "data": {
        "entry_id": 999,
        "user": {
            "telegram_id": YOUR_TELEGRAM_ID,
            "email": "test@hhivp.com",
            "first_name": "Test",
            "username": "test_user"
        },
        "work_entry": {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "company": "Тестовая компания",
            "duration": "30 мин",
            "description": "Тестовое описание работ для проверки интеграции с n8n и Google Sheets",
            "is_travel": False,
            "workers": ["Тимофей", "Дима"],
            "workers_count": 2
        },
        "creator": {
            "name": "TestUser",
            "telegram_id": YOUR_TELEGRAM_ID
        }
    }
}

async def test_n8n_integration(webhook_url: str, webhook_secret: str = None) -> Dict[str, Any]:
    """
    Тестирует интеграцию с n8n webhook
    """
    print(f"🔗 Тестирование n8n интеграции...")
    print(f"URL: {webhook_url}")
    
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "HHIVP-Telegram-Bot/1.0"
    }
    
    if webhook_secret:
        headers["X-API-Key"] = webhook_secret
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                webhook_url,
                json=TEST_WEBHOOK_DATA,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                
                result = {
                    "success": response.status == 200,
                    "status_code": response.status,
                    "headers": dict(response.headers),
                    "response_text": await response.text()
                }
                
                if response.content_type == "application/json":
                    try:
                        result["response_json"] = await response.json()
                    except:
                        pass
                
                return result
                
    except asyncio.TimeoutError:
        return {
            "success": False,
            "error": "Timeout - n8n не отвечает в течение 30 секунд"
        }
    except aiohttp.ClientError as e:
        return {
            "success": False,
            "error": f"Ошибка подключения: {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Неожиданная ошибка: {str(e)}"
        }

def print_test_results(results: Dict[str, Any]):
    """
    Выводит результаты тестирования
    """
    print("\n" + "="*60)
    print("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
    print("="*60)
    
    if results["success"]:
        print("✅ Статус: УСПЕШНО")
        print(f"📡 HTTP статус: {results['status_code']}")
        
        if "response_json" in results:
            print("📄 Ответ от n8n:")
            print(json.dumps(results["response_json"], indent=2, ensure_ascii=False))
        else:
            print("📄 Ответ от n8n (текст):")
            print(results["response_text"][:500])
            
    else:
        print("❌ Статус: ОШИБКА")
        if "status_code" in results:
            print(f"📡 HTTP статус: {results['status_code']}")
        print(f"🚨 Ошибка: {results.get('error', 'Неизвестная ошибка')}")
        
        if "response_text" in results:
            print("📄 Ответ сервера:")
            print(results["response_text"][:500])
    
    print("="*60)

def print_test_data():
    """
    Выводит тестовые данные
    """
    print("📋 ТЕСТОВЫЕ ДАННЫЕ")
    print("="*40)
    print(json.dumps(TEST_WEBHOOK_DATA, indent=2, ensure_ascii=False))
    print("="*40)

async def main():
    """
    Основная функция тестирования
    """
    print("🧪 ТЕСТ ИНТЕГРАЦИИ N8N И GOOGLE SHEETS")
    print("="*60)
    
    # Проверяем аргументы командной строки
    if len(sys.argv) < 2:
        print("❌ Ошибка: Не указан URL webhook")
        print("\nИспользование:")
        print(f"  python3 {sys.argv[0]} <WEBHOOK_URL> [SECRET_KEY]")
        print("\nПример:")
        print(f"  python3 {sys.argv[0]} https://your-n8n-instance.com/webhook/work-journal")
        return
    
    webhook_url = sys.argv[1]
    webhook_secret = sys.argv[2] if len(sys.argv) > 2 else None
    
    print_test_data()
    
    # Запускаем тест
    results = await test_n8n_integration(webhook_url, webhook_secret)
    
    # Выводим результаты
    print_test_results(results)
    
    # Рекомендации
    print("\n💡 РЕКОМЕНДАЦИИ:")
    if results["success"]:
        print("✅ Интеграция работает корректно!")
        print("🔍 Проверьте Google Sheets - должна появиться новая запись")
        print("📊 Проверьте логи n8n workflow для детальной информации")
    else:
        print("❌ Интеграция не работает. Возможные причины:")
        print("  • Неправильный URL webhook")
        print("  • n8n workflow не активирован")
        print("  • Ошибки в настройке Google Sheets API")
        print("  • Проблемы с аутентификацией")
        print("  • Сетевые проблемы")
        
    print("\n🔧 СЛЕДУЮЩИЕ ШАГИ:")
    print("1. Проверьте n8n workflow активирован")
    print("2. Проверьте Google Sheets ID в настройках")
    print("3. Проверьте Service Account права доступа")
    print("4. Посмотрите логи n8n для детальной диагностики")

if __name__ == "__main__":
    asyncio.run(main())
