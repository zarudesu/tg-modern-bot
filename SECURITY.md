# 🔐 Безопасность

## Общие принципы

### 🛡️ Защита данных
- Все секреты в переменных окружения
- Никаких hardcoded токенов в коде
- .env файлы исключены из git

### 🔒 Аутентификация
- Проверка админских прав
- Валидация пользователей
- Логирование всех действий

### 🚫 Валидация входных данных
- Все пользовательские данные валидируются
- Защита от SQL injection через ORM
- Санитизация markdown текста

## Конфигурация безопасности

### Переменные окружения (.env):
```env
# НИКОГДА не коммитить в git!
TELEGRAM_TOKEN=your_secret_token
ADMIN_USER_ID=your_admin_id

# Дополнительная защита
WEBHOOK_SECRET=random_secret_string
SESSION_TIMEOUT=3600
```

### Rate Limiting:
```env
RATE_LIMIT_DEFAULT=10/minute
RATE_LIMIT_SEARCH=30/minute
RATE_LIMIT_ADMIN=100/minute
```

## Уровни доступа

### 👤 Обычные пользователи:
- `/start`, `/help` - базовые команды
- `/journal`, `/history` - журнал работ
- Только свои данные

### 👑 Администраторы:
- Все пользовательские команды +
- `/settings` - настройки системы
- Email обработка для daily tasks
- Управление пользователями

### Проверка прав:
```python
@router.message(Command("admin_command"))
async def admin_only(message: Message):
    if message.from_user.id not in settings.admin_user_id_list:
        await message.answer("❌ Недостаточно прав")
        return
    # Админская логика
```

## Защита от атак

### SQL Injection:
```python
# ✅ Безопасно - через ORM
result = await session.execute(
    select(User).where(User.telegram_id == user_id)
)

# ❌ Небезопасно - никогда так не делать
# query = f"SELECT * FROM users WHERE id = {user_id}"
```

### XSS в Markdown:
```python
def escape_markdown_v2(text: str) -> str:
    """Экранирование специальных символов"""
    escape_chars = ['\\', '`', '*', '_', '{', '}', '[', ']', 
                   '(', ')', '#', '+', '-', '.', '!', '|', '~', '>']
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    return text
```

### Rate Limiting:
```python
# Автоматическое ограничение в middleware
class RateLimitMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        # Проверка лимитов
        if await self.is_rate_limited(event.from_user.id):
            return  # Блокируем
        return await handler(event, data)
```

## Логирование безопасности

### Что логируется:
```python
# Успешные действия
bot_logger.info(f"User {user_id} executed command {command}")

# Попытки нарушения
bot_logger.warning(f"Non-admin user {user_id} tried admin function")

# Ошибки безопасности  
bot_logger.error(f"Rate limit exceeded for user {user_id}")
```

### Что НЕ логируется:
- ❌ Токены и пароли
- ❌ Полные email адреса (только домен)
- ❌ Личные данные пользователей

## Секреты в продакшене

### Docker Secrets (рекомендуемо):
```yaml
# docker-compose.prod.yml
services:
  telegram-bot:
    secrets:
      - telegram_token
      - database_password
    environment:
      TELEGRAM_TOKEN_FILE: /run/secrets/telegram_token

secrets:
  telegram_token:
    external: true
  database_password:
    external: true
```

### Vault интеграция:
```python
import hvac

client = hvac.Client(url='https://vault.company.com')
secret = client.secrets.kv.v2.read_secret_version(
    path='telegram-bot/production'
)
```

## Сетевая безопасность

### Firewall правила:
```bash
# Разрешить только необходимые порты
sudo ufw allow ssh
sudo ufw allow 443/tcp  # HTTPS
sudo ufw deny 5432/tcp  # PostgreSQL (только internal)
```

### SSL/TLS:
```bash
# Let's Encrypt сертификаты
certbot certonly --standalone -d your-bot-domain.com
```

### Webhook безопасность:
```python
@app.route("/webhook", methods=["POST"])
async def webhook_handler(request):
    # Проверка подписи
    if not verify_webhook_signature(request):
        return web.Response(status=401)
    # Обработка
```

## Мониторинг безопасности

### Алерты:
- Неудачные попытки аутентификации
- Превышение rate limits
- Подозрительная активность
- Ошибки в критических функциях

### Метрики:
```python
# Счетчики безопасности
security_events = {
    'failed_auth': 0,
    'rate_limit_hits': 0,
    'admin_actions': 0
}
```

## Резервное копирование

### Что бэкапить:
- ✅ База данных (зашифровано)
- ✅ Конфигурационные файлы
- ✅ Логи (last 30 days)

### Что НЕ бэкапить:
- ❌ .env файлы
- ❌ Временные токены
- ❌ Cache данные

### Шифрование бэкапов:
```bash
# GPG шифрование
gpg --symmetric --cipher-algo AES256 backup.sql
```

## Обновления безопасности

### Регулярные действия:
1. **Еженедельно**: обновление зависимостей
2. **Ежемесячно**: ротация секретов
3. **Ежеквартально**: аудит безопасности

### Мониторинг уязвимостей:
```bash
# Проверка Python зависимостей
pip-audit

# Проверка Docker образов
docker scout cves
```

## Incident Response

### При компрометации:
1. **Немедленно**: отозвать все токены
2. **В течение часа**: сменить пароли БД
3. **В течение дня**: полный аудит логов

### Контакты:
- Telegram: уведомление админов
- Email: критические инциденты
- Мониторинг: автоматические алерты

## Compliance

### GDPR соответствие:
- Пользователи могут запросить удаление данных
- Логирование согласий
- Минимизация собираемых данных

### Аудит логи:
```python
audit_logger.info({
    'action': 'user_data_deleted',
    'user_id': user_id,
    'admin_id': admin_id,
    'timestamp': datetime.utcnow()
})
```

## Чеклист безопасности

### Перед развертыванием:
- [ ] Все секреты в переменных окружения
- [ ] .env добавлен в .gitignore
- [ ] Rate limiting настроен
- [ ] Логирование работает
- [ ] Firewall настроен
- [ ] SSL сертификаты установлены
- [ ] Резервное копирование настроено

### Регулярные проверки:
- [ ] Обновления безопасности применены
- [ ] Логи проанализированы
- [ ] Метрики проверены
- [ ] Секреты ротированы
- [ ] Доступы актуализированы

Помните: **Безопасность - это процесс, а не одноразовое действие!**
