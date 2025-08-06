"""
Утилиты для работы с форматированием времени
"""
import re
from typing import Optional


def parse_duration_to_minutes(duration_str: str) -> Optional[int]:
    """
    Преобразует строку времени в минуты
    
    Примеры:
    - "1 час" -> 60
    - "30 мин" -> 30
    - "2 часа" -> 120
    - "1.5 часа" -> 90
    - "90 мин" -> 90
    - "2ч 30м" -> 150
    """
    if not duration_str or not isinstance(duration_str, str):
        return None
    
    duration_str = duration_str.lower().strip()
    total_minutes = 0
    
    # Паттерны для разных форматов
    patterns = [
        # "2 часа", "1 час", "0.5 часа"
        (r'(\d+(?:\.\d+)?)\s*(?:час[аов]?|ч)', lambda x: float(x) * 60),
        # "30 мин", "30 минут", "30м"
        (r'(\d+(?:\.\d+)?)\s*(?:мин[уты]?|м)', lambda x: float(x)),
        # Чистые числа - считаем минутами
        (r'^(\d+(?:\.\d+)?)$', lambda x: float(x)),
    ]
    
    found_match = False
    
    for pattern, converter in patterns:
        matches = re.findall(pattern, duration_str)
        for match in matches:
            total_minutes += converter(match)
            found_match = True
    
    if not found_match:
        # Пытаемся найти числа и считаем их минутами
        numbers = re.findall(r'\d+(?:\.\d+)?', duration_str)
        if numbers:
            total_minutes = float(numbers[0])
    
    return int(round(total_minutes)) if total_minutes > 0 else None


def format_duration_display(duration_str: str) -> str:
    """
    Форматирует время для отображения пользователю
    
    Примеры:
    - "90" -> "90 мин (1ч 30м)"
    - "60" -> "60 мин (1 час)"
    - "30" -> "30 мин"
    """
    minutes = parse_duration_to_minutes(duration_str)
    
    if not minutes:
        return duration_str  # Возвращаем как есть если не смогли распарсить
    
    if minutes < 60:
        return f"{minutes} мин"
    
    hours = minutes // 60
    remaining_minutes = minutes % 60
    
    if remaining_minutes == 0:
        if hours == 1:
            return f"{minutes} мин (1 час)"
        else:
            return f"{minutes} мин ({hours} часов)"
    else:
        if hours == 1:
            return f"{minutes} мин (1ч {remaining_minutes}м)"
        else:
            return f"{minutes} мин ({hours}ч {remaining_minutes}м)"


def format_duration_for_n8n(duration_str: str) -> int:
    """
    Форматирует время для отправки в n8n (всегда в минутах)
    
    Returns:
        int: Время в минутах
    """
    minutes = parse_duration_to_minutes(duration_str)
    return minutes if minutes is not None else 0


# Тесты функций
if __name__ == "__main__":
    test_cases = [
        "1 час",
        "30 мин", 
        "2 часа",
        "1.5 часа",
        "90 мин",
        "2ч 30м",
        "45",
        "90",
        "120",
        "1час 15мин",
        "2 часа 30 минут"
    ]
    
    print("Тестирование парсинга времени:")
    for case in test_cases:
        minutes = parse_duration_to_minutes(case)
        display = format_duration_display(case)
        n8n_format = format_duration_for_n8n(case)
        print(f"{case:15} -> {minutes:3} мин | Display: {display:20} | n8n: {n8n_format}")
