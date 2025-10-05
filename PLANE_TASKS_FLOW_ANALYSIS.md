# 📊 Plane Tasks Flow Analysis - Логика загрузки задач

## 🎯 Общая архитектура

### Система кэширования задач (3-уровневая)

```
┌─────────────────────────────────────────────────────────────┐
│ 1. TELEGRAM BOT (Frontend)                                  │
│    /daily_tasks → показывает кэшированные задачи           │
│    /daily_settings → настройки email + уведомления          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. USER_TASKS_CACHE_SERVICE (Background Worker)            │
│    - Асинхронная загрузка задач в фоне (~5 минут)          │
│    - Уведомления о начале/завершении                        │
│    - Таблица: user_tasks_cache (кэш задач)                  │
│    - Таблица: user_tasks_sync_status (статус синхронизации) │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. PLANE_API_CLIENT (API Integration)                      │
│    - Rate limiting: 60 req/min (1 req/sec)                  │
│    - Адаптивные задержки при приближении к лимиту           │
│    - Кэш проектов (4 часа)                                  │
│    - Кэш участников + states (1 час)                        │
│    - Retry механизм с exponential backoff                   │
└─────────────────────────────────────────────────────────────┘
```

## 📋 Детальный Flow загрузки задач

### Шаг 1: Пользователь нажимает `/daily_tasks`

**Файл:** `app/modules/daily_tasks/handlers.py:32`

```python
@router.message(Command("daily_tasks"))
async def cmd_daily_tasks(message: Message):
    # 1. Проверка админ прав
    # 2. Загружаем настройки из БД
    admin_settings = daily_tasks_service.admin_settings.get(admin_id, {})
    admin_email = admin_settings.get('plane_email')

    # 3. Если email не настроен → просим настроить
    if not admin_email:
        return show_setup_email_prompt()

    # 4. 🚀 БЫСТРЫЙ ПУТЬ: Получаем из КЭША
    cached_tasks = await user_tasks_cache_service.get_cached_tasks(
        user_email=admin_email,
        max_tasks=50
    )

    # 5. Проверяем статус синхронизации
    sync_status = await user_tasks_cache_service.get_sync_status(admin_email)
```

### Шаг 2: Сценарии обработки

#### Сценарий A: Задачи загружаются (sync_in_progress=True)
```python
if not cached_tasks and sync_status.sync_in_progress:
    return "⏳ Загрузка задач в процессе... Это займет ~5 минут"
```

#### Сценарий B: Нет задач вообще
```python
if not cached_tasks:
    return "📋 Найдено задач: 0"
```

#### Сценарий C: ✅ Задачи найдены в кэше
```python
# Показываем первые 5 задач с красивым форматированием
# Эмодзи приоритета, состояния, ссылки на Plane
```

### Шаг 3: Первая синхронизация (если кэша нет)

**Триггер:** Вызывается автоматически при первом запросе задач

**Файл:** `app/services/user_tasks_cache_service.py:23`

```python
async def start_user_sync(user_email: str, telegram_user_id: int):
    # 1. Проверяем, не идет ли уже синхронизация
    if sync_status and sync_status.sync_in_progress:
        return False  # Уже загружается

    # 2. Создаем/обновляем статус синхронизации
    sync_status.sync_in_progress = True
    sync_status.last_sync_started = datetime.now()

    # 3. 📨 Отправляем уведомление пользователю
    await bot.send_message(
        telegram_user_id,
        "⏳ Загружаем ваши задачи из Plane.so... Это займет ~5 минут"
    )

    # 4. 🚀 Запускаем ФОНОВУЮ задачу (не блокируем UI)
    asyncio.create_task(self._sync_user_tasks_background(user_email))
```

### Шаг 4: Фоновая загрузка задач

**Файл:** `app/services/user_tasks_cache_service.py:80`

```python
async def _sync_user_tasks_background(user_email: str):
    try:
        # 1. 📥 Получаем задачи из Plane API (долгий процесс!)
        tasks = await plane_api.get_user_tasks(user_email)
        # ⏱️ Занимает ~3-5 минут из-за rate limiting

        # 2. Фильтруем активные задачи (без done/cancelled)
        active_tasks = [t for t in tasks if t.state not in ['done', 'completed']]

        # 3. 💾 Сохраняем в базу данных
        tasks_count = await self._save_tasks_to_cache(user_email, active_tasks)

        # 4. ✅ Обновляем статус синхронизации
        sync_status.sync_in_progress = False
        sync_status.last_sync_completed = datetime.now()
        sync_status.total_tasks_found = tasks_count

        # 5. 📨 Уведомляем пользователя о завершении
        await bot.send_message(
            telegram_user_id,
            f"✅ Задачи загружены! Найдено: {tasks_count}"
        )

    except Exception as e:
        # ❌ Сохраняем ошибку в БД
        sync_status.last_sync_error = str(e)
        await bot.send_message(telegram_user_id, "❌ Ошибка загрузки")
```

## 🔥 Plane API - Детальная логика

**Файл:** `app/integrations/plane_api.py:277`

### Метод: `get_user_tasks(user_email)`

```python
async def get_user_tasks(self, user_email: str) -> List[PlaneTask]:
    """
    ДОЛГИЙ ПРОЦЕСС (~3-5 минут) из-за множества запросов к API
    """

    async with aiohttp.ClientSession() as session:
        # ЭТАП 1: Получаем список всех проектов (1 запрос)
        projects = await self._get_projects(session)
        # Результат кэшируется на 4 часа

        # ЭТАП 2: Для КАЖДОГО проекта получаем участников и states
        # 🐌 УЗКОЕ МЕСТО: Если 20 проектов = 40 запросов
        for project in projects:
            members = await self._get_project_members(session, project_id)
            # ⏱️ + Rate limiting delay = 1 second между запросами

            states = await self._get_project_states(session, project_id)
            # ⏱️ + еще 1 second delay

        # ЭТАП 3: Строим мапинг user_id -> email
        user_id_to_email = {}  # Ищем ID пользователя по email
        for member in all_members:
            if member['email'] == user_email:
                target_user_id = member['id']

        # ❌ ПРОБЛЕМА: Если email не найден в участниках
        if user_email not in user_id_to_email.values():
            bot_logger.warning(f"User {user_email} NOT found in any project!")
            # Возвращаем ПУСТОЙ список (но БЕЗ ошибки!)
            return []

        # ЭТАП 4: Получаем задачи из КАЖДОГО проекта
        all_tasks = []
        for project in projects:
            # 🐌 ЕЩЕ ОДНО УЗКОЕ МЕСТО
            tasks = await self._get_project_issues(
                session, project_id, user_email, user_id_to_email
            )
            # ⏱️ + 1-2 seconds на каждый проект
            all_tasks.extend(tasks)

        return all_tasks  # Возвращаем все найденные задачи
```

### Rate Limiting механизм

**Файл:** `app/integrations/plane_api.py:167`

```python
# Plane.so лимиты: 60 запросов в минуту
_request_delay = 1.0 секунда  # Базовая задержка

async def _rate_limit_delay(self):
    # Если осталось мало запросов (<= 5)
    if self._rate_limit_remaining <= 5:
        adaptive_delay = self._request_delay * 2  # ❗ Удваиваем delay!
        await sleep(adaptive_delay)  # 2 секунды вместо 1

    # Обычная задержка
    await sleep(self._request_delay)  # 1 секунда
```

### Обработка HTTP 429 (Rate Limit Exceeded)

```python
if response.status == 429:
    retry_after = response.headers.get('Retry-After', 60)
    bot_logger.warning(f"Rate limit! Waiting {retry_after}s")
    await sleep(retry_after)  # Ждем до сброса лимита
```

## 🐛 Текущие проблемы

### Проблема 1: ❌ Несуществующий email → зависание

**Причина:**
```python
# В Plane API: Если email не найден
if user_email not in user_id_to_email.values():
    return []  # Возвращаем пустой список без ошибки
```

**Что происходит:**
1. Пользователь вводит `nonexistent@test.com`
2. Plane API перебирает ВСЕ проекты и всех участников (~3-5 мин)
3. Не находит email → возвращает `[]`
4. Кэш сервис: "Синхронизация завершена, найдено 0 задач"
5. Пользователю: "📋 Найдено задач: 0" (без указания причины!)

**Решение:**
- Добавить **EARLY RETURN** после первых 2-3 проектов, если email не найден
- Вернуть явную ошибку вместо пустого списка
- Показать пользователю "Email не найден в Plane"

### Проблема 2: 🔴 Toggle notifications не работает

**Причина:**
```python
@router.callback_query(F.data == "toggle_notifications")
async def callback_toggle_notifications(callback: CallbackQuery):
    # ... переключаем состояние ...
    await daily_tasks_service._save_admin_settings_to_db()

    # ❌ ОТСУТСТВУЕТ: await callback.answer()
    # ❌ НЕТ: возврата к меню настроек
```

**Что происходит:**
- Callback не закрывается (крутится "Loading...")
- UI зависает

**Решение:**
```python
await callback.answer(f"✅ Уведомления {'включены' if new_state else 'отключены'}")
await callback_back_to_settings(callback)  # Обновляем меню
```

### Проблема 3: ⏱️ Нет таймаутов на HTTP запросы

**Причина:**
```python
async with session.request(method, url, **kwargs) as response:
    # ❌ НЕТ TIMEOUT параметра!
```

**Что происходит:**
- Если Plane API медленно отвечает → ждем бесконечно
- Блокирует фоновую синхронизацию

**Решение:**
```python
timeout = aiohttp.ClientTimeout(total=30, connect=10)
async with session.request(method, url, timeout=timeout, **kwargs):
    ...
```

## ✅ Рекомендации

1. **Добавить таймауты:** 30 секунд на запрос к Plane API
2. **Early return для несуществующих email:** Проверять после первых 3 проектов
3. **Исправить toggle_notifications:** Добавить `callback.answer()` и обновление меню
4. **Улучшить сообщения об ошибках:** Показывать причину (email не найден, API недоступен)
5. **Кэширование агрессивнее:** Увеличить кэш проектов с 4 до 24 часов
6. **Прогресс индикатор:** Показывать "Обработано 5/20 проектов..." во время загрузки

## 📊 Оценка времени загрузки

**Для пользователя с 20 проектами:**

```
Проекты (1 req)               = 1 сек
Участники (20 req × 1s)       = 20 сек
States (20 req × 1s)           = 20 сек
Issues (20 req × 1-2s)         = 30 сек
Обработка + фильтрация         = 10 сек
                              ─────────
ИТОГО                         ≈ 81 сек (~1.5 минуты)
```

**При adaptive delay (близко к лимиту):**
```
81 сек × 2 = 162 сек (2.7 минуты)
```

**Вывод:** Реальное время загрузки 2-5 минут в зависимости от количества проектов и rate limiting.
