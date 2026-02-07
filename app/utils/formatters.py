"""
Утилиты для форматирования сообщений Telegram
"""
from typing import Dict, Any, List, Optional
from datetime import datetime


def escape_markdown(text: str) -> str:
    """Экранирование символов для Markdown"""
    if not text:
        return ""
    
    escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    return text


def format_device_info(device: Dict[str, Any]) -> str:
    """Форматирование информации об устройстве"""
    name = escape_markdown(device.get('name', 'N/A'))
    device_type = device.get('device_type', {})
    device_type_name = escape_markdown(device_type.get('display', 'Unknown'))
    
    site = device.get('site', {})
    site_name = escape_markdown(site.get('name', 'N/A'))
    
    status = device.get('status', {})
    status_label = escape_markdown(status.get('label', 'Unknown'))
    
    role = device.get('role', {})
    role_name = escape_markdown(role.get('name', 'N/A'))
    
    # Основная информация
    message = f"🖥️ *Устройство:* {name}\n"
    message += f"📱 *Тип:* {device_type_name}\n"
    message += f"🏢 *Сайт:* {site_name}\n"
    message += f"🔧 *Роль:* {role_name}\n"
    message += f"📊 *Статус:* {status_label}\n"
    
    # IP адреса
    primary_ip4 = device.get('primary_ip4')
    if primary_ip4:
        ip_display = escape_markdown(primary_ip4.get('display', ''))
        message += f"🌐 *IP адрес:* {ip_display}\n"
    
    # Серийный номер
    serial = device.get('serial', '')
    if serial:
        message += f"🔢 *Серийный номер:* {escape_markdown(serial)}\n"
    
    # Asset tag
    asset_tag = device.get('asset_tag', '')
    if asset_tag:
        message += f"🏷️ *Asset Tag:* {escape_markdown(asset_tag)}\n"
    
    # Описание
    description = device.get('description', '')
    if description:
        message += f"📝 *Описание:* {escape_markdown(description)}\n"
    
    # Координаты
    latitude = device.get('latitude')
    longitude = device.get('longitude')
    if latitude and longitude:
        message += f"📍 *Координаты:* {latitude}, {longitude}\n"
    
    # Кластер
    cluster = device.get('cluster')
    if cluster:
        cluster_name = escape_markdown(cluster.get('name', ''))
        message += f"☁️ *Кластер:* {cluster_name}\n"
    
    return message


def format_site_info(site: Dict[str, Any]) -> str:
    """Форматирование информации о сайте"""
    name = escape_markdown(site.get('name', 'N/A'))
    slug = escape_markdown(site.get('slug', 'N/A'))
    
    status = site.get('status', {})
    status_label = escape_markdown(status.get('label', 'Unknown'))
    
    region = site.get('region', {})
    region_name = escape_markdown(region.get('name', 'N/A')) if region else 'N/A'
    
    message = f"🏢 *Сайт:* {name}\n"
    message += f"🔗 *Slug:* {slug}\n"
    message += f"🌍 *Регион:* {region_name}\n"
    message += f"📊 *Статус:* {status_label}\n"
    
    # Описание
    description = site.get('description', '')
    if description:
        message += f"📝 *Описание:* {escape_markdown(description)}\n"
    
    # Физический адрес
    physical_address = site.get('physical_address', '')
    if physical_address:
        message += f"📍 *Адрес:* {escape_markdown(physical_address)}\n"
    
    # Контакты
    contact_name = site.get('contact_name', '')
    contact_phone = site.get('contact_phone', '')
    contact_email = site.get('contact_email', '')
    
    if contact_name or contact_phone or contact_email:
        message += "\n👤 *Контакты:*\n"
        if contact_name:
            message += f"  • Имя: {escape_markdown(contact_name)}\n"
        if contact_phone:
            message += f"  • Телефон: {escape_markdown(contact_phone)}\n"
        if contact_email:
            message += f"  • Email: {escape_markdown(contact_email)}\n"
    
    return message


def format_search_results(results: Dict[str, List[Dict]], query: str) -> str:
    """Форматирование результатов поиска"""
    escaped_query = escape_markdown(query)
    message = f"🔍 *Результаты поиска по запросу:* {escaped_query}\n\n"
    
    total_results = sum(len(items) for items in results.values())
    
    if total_results == 0:
        return f"🔍 По запросу *{escaped_query}* ничего не найдено\\."
    
    # Устройства
    devices = results.get('devices', [])
    if devices:
        message += "🖥️ *Устройства:*\n"
        for i, device in enumerate(devices[:5], 1):
            name = escape_markdown(device.get('name', 'N/A'))
            device_type = device.get('device_type', {})
            type_name = escape_markdown(device_type.get('display', 'Unknown'))
            message += f"  {i}\\. {name} \\({type_name}\\)\n"
        
        if len(devices) > 5:
            message += f"  \\.\\.\\. и еще {len(devices) - 5} устройств\n"
        message += "\n"
    
    # Сайты
    sites = results.get('sites', [])
    if sites:
        message += "🏢 *Сайты:*\n"
        for i, site in enumerate(sites[:5], 1):
            name = escape_markdown(site.get('name', 'N/A'))
            region = site.get('region', {})
            region_name = escape_markdown(region.get('name', '')) if region else ''
            location_info = f" \\({region_name}\\)" if region_name else ""
            message += f"  {i}\\. {name}{location_info}\n"
        
        if len(sites) > 5:
            message += f"  \\.\\.\\. и еще {len(sites) - 5} сайтов\n"
        message += "\n"
    
    # IP адреса
    ip_addresses = results.get('ip_addresses', [])
    if ip_addresses:
        message += "🌐 *IP адреса:*\n"
        for i, ip in enumerate(ip_addresses[:5], 1):
            address = escape_markdown(ip.get('display', 'N/A'))
            description = ip.get('description', '')
            desc_text = f" \\- {escape_markdown(description)}" if description else ""
            message += f"  {i}\\. {address}{desc_text}\n"
        
        if len(ip_addresses) > 5:
            message += f"  \\.\\.\\. и еще {len(ip_addresses) - 5} адресов\n"
        message += "\n"
    
    return message.rstrip()


def format_error_message(error_type: str, details: str = "") -> str:
    """Форматирование сообщений об ошибках"""
    error_messages = {
        "api_error": "🔌 Ошибка подключения к API\\. Попробуйте позже\\.",
        "auth_error": "🔒 Недостаточно прав для выполнения операции\\.",
        "validation_error": "⚠️ Некорректные данные\\. Проверьте ввод\\.",
        "not_found": "❌ Запрашиваемый объект не найден\\.",
        "timeout": "⏱️ Превышено время ожидания ответа\\.",
        "rate_limit": "🚦 Превышен лимит запросов\\. Подождите немного\\.",
        "unknown": "❌ Произошла неизвестная ошибка\\."
    }
    
    base_message = error_messages.get(error_type, error_messages["unknown"])
    
    if details:
        escaped_details = escape_markdown(details)
        return f"{base_message}\n\n*Детали:* {escaped_details}"
    
    return base_message


def format_help_message() -> str:
    """Форматирование справки по командам"""
    return (
        "🤖 *HHIVP IT Assistant \\— Справка*\n\n"

        "*🤖 PLANE AI АССИСТЕНТ*  \\(только админы\\)\n"
        "Спроси что угодно о задачах на естественном языке:\n"
        "  `/plane чем мне заняться?`\n"
        "  `/plane какие срочные задачи?`\n"
        "  `/plane что по проекту HARZL?`\n"
        "  `/plane закрой #123`\n"
        "  `/plane назначь #456 на Тимофея`\n"
        "  `/plane создай задачу в HG: бэкапы`\n"
        "🎤 Голосовые сообщения тоже работают\n"
        "Выход из режима: `/plane_exit`\n\n"

        "*✈️ ЗАДАЧИ ИЗ PLANE*  \\(только админы\\)\n"
        "📋 `/daily_tasks` \\— мои задачи на сегодня\n"
        "⚙️ `/daily_settings` \\— настройки уведомлений\n"
        "☀️ _Утренний дайджест: AI\\-сводка в 09:00_\n"
        "_\\(TOP\\-3 приоритета, просроченные, рекомендации\\)_\n\n"

        "*📝 ЗАЯВКИ В ПОДДЕРЖКУ*  \\(в группе клиента\\)\n"
        "Доступно всем участникам группы:\n"
        "1\\. Реплайните сообщение бота в чате клиента\n"
        "2\\. Бот пишет во внутренний чат: «создать задачу»\n"
        "3\\. Заполняете детали задачи\n"
        "4\\. Бот отвечает клиенту что задача создана\n"
        "Или: `/request` → текст проблемы\n\n"

        "*📋 ЖУРНАЛ РАБОТ*  \\(только админы\\)\n"
        "📝 Создать запись \\— кнопка в меню\n"
        "📊 `/history` \\— история записей\n"
        "📈 `/report` \\— отчёты и статистика\n"
        "🔄 `/sheets_sync` \\— синхронизация с Google Sheets\n\n"

        "*🔧 ДИАГНОСТИКА*  \\(только админы\\)\n"
        "🩺 `/diag` \\— диагностика всех систем\n"
        "📊 `/plane_status` \\— статус Plane интеграции\n"
        "🔍 `/plane_audit` \\— аудит задач Plane\n\n"

        "*⚙️ НАСТРОЙКИ*  \\(только админы\\)\n"
        "⚙️ `/daily_settings` \\— время уведомлений, email\n"
        "⚙️ `/setup_chat` \\— привязать чат к проекту Plane\n"
        "📋 `/list_mappings` \\— список привязанных чатов\n"
        "👤 `/profile` \\| 🏓 `/ping`"
    )


def format_about_message() -> str:
    """Полное описание всех функций бота (HTML)"""
    return (
        "<b>🤖 HHIVP IT Assistant — О боте</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"

        "<b>🤖 PLANE AI АССИСТЕНТ</b>\n"
        "Спроси что угодно о задачах на естественном языке.\n"
        "AI проанализирует данные из Plane и ответит.\n"
        "• <code>/plane чем мне заняться?</code>\n"
        "• <code>/plane какие срочные задачи?</code>\n"
        "• <code>/plane что по проекту HARZL?</code>\n"
        "• <code>/plane закрой #123</code>\n"
        "• <code>/plane назначь #456 на Тимофея</code>\n"
        "• <code>/plane создай задачу в HG: бэкапы</code>\n"
        "🎤 Голосовые сообщения тоже работают\n"
        "Выход: /plane_exit\n\n"

        "<b>📋 СОЗДАНИЕ ЗАДАЧ</b>\n"
        "Интерактивный черновик:\n"
        "→ AI распознаёт проект, название, приоритет\n"
        "→ Показывает карточку с кнопками приоритета\n"
        "→ Пиши на естественном языке чтобы уточнить:\n"
        '  <i>"срочно"</i>, <i>"на Тимофея"</i>, '
        '<i>"дедлайн завтра"</i>, <i>"описание: ..."</i>\n'
        "→ Нажми «Создать» когда готово\n\n"

        "<b>✈️ ЗАДАЧИ ИЗ PLANE</b>\n"
        "• /daily_tasks — задачи на сегодня\n"
        "• /daily_settings — время уведомлений, email\n"
        "• <b>Утренний дайджест 09:00</b> — AI-сводка:\n"
        "  TOP-3 приоритета, просроченные, рекомендации\n\n"

        "<b>📝 ЗАЯВКИ В ПОДДЕРЖКУ</b> <i>(в группе клиента)</i>\n"
        "1. Реплайните сообщение бота в чате клиента\n"
        "2. Бот пишет во внутренний чат «создать задачу»\n"
        "3. Заполняете детали\n"
        "4. Бот отвечает клиенту что задача создана\n"
        "Или: /request — текст проблемы\n\n"

        "<b>📋 ЖУРНАЛ РАБОТ</b>\n"
        "• Кнопка «Новая запись» → дата → компания\n"
        "  → исполнитель → описание → сохранение\n"
        "• /history — последние записи\n"
        "• /report — статистика за неделю\n"
        "• /sheets_sync — синхронизация с Google Sheets\n\n"

        "<b>🔧 ДИАГНОСТИКА</b>\n"
        "• /diag — здоровье: БД, Redis, Plane, AI\n"
        "• /plane_status — задачи по статусам, зависшие\n"
        "• /plane_audit — аудит: просроченные, нагрузка\n\n"

        "<b>🧠 SMART AI ДЕТЕКЦИЯ</b>\n"
        "Бот слушает групповые чаты. Если видит проблему —\n"
        "предлагает создать задачу в Plane автоматически.\n"
        "Кнопки: Создать / Не задача / Редактировать\n\n"

        "<b>📨 PLANE → TELEGRAM</b>\n"
        "Уведомления из Plane прямо в Telegram:\n"
        "новые задачи, комментарии, смена статуса\n\n"

        "<b>⚙️ НАСТРОЙКИ</b>\n"
        "• /daily_settings — уведомления, email\n"
        "• /setup_chat — привязать группу к проекту\n"
        "• /list_mappings — привязанные чаты\n"
        "• /profile — профиль\n"
        "• /ping — проверка\n\n"

        "━━━━━━━━━━━━━━━━━━━━\n"
        "AI: Groq + OpenRouter (fallback)\n"
        "4 AI-провайдера · 11 модулей · 30+ команд"
    )


def format_user_profile(user: Dict[str, Any]) -> str:
    """Форматирование профиля пользователя"""
    username = escape_markdown(user.get('username', 'N/A'))
    first_name = escape_markdown(user.get('first_name', 'N/A'))
    role = escape_markdown(user.get('role', 'guest'))
    
    created_at = user.get('created_at')
    if isinstance(created_at, datetime):
        created_date = created_at.strftime('%d.%m.%Y %H:%M')
    else:
        created_date = 'N/A'
    
    last_seen = user.get('last_seen')
    if isinstance(last_seen, datetime):
        last_seen_date = last_seen.strftime('%d.%m.%Y %H:%M')
    else:
        last_seen_date = 'N/A'
    
    message = f"👤 *Профиль пользователя*\n\n"
    message += f"🏷️ *Username:* @{username}\n"
    message += f"👋 *Имя:* {first_name}\n"
    message += f"🔧 *Роль:* {role}\n"
    message += f"📅 *Регистрация:* {escape_markdown(created_date)}\n"
    message += f"🕐 *Последняя активность:* {escape_markdown(last_seen_date)}\n"
    
    return message
