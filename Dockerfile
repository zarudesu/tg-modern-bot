FROM python:3.11-slim

# Метаданные
LABEL name="HHIVP IT Assistant" \
      version="1.1.0" \
      description="Telegram Bot for IT work management"

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Создаем рабочую директорию
WORKDIR /app

# Копируем файлы зависимостей
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код приложения
COPY app/ ./app/
COPY sql/ ./sql/
COPY alembic/ ./alembic/
COPY alembic.ini ./

# Создаем необходимые директории
RUN mkdir -p logs backups

# Создаем пользователя для безопасности
RUN useradd -m -u 1000 botuser && chown -R botuser:botuser /app
USER botuser

# Настраиваем переменные окружения
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=60s --timeout=30s --start-period=40s --retries=3 \
    CMD python -c "import asyncio; from app.main import health_check; asyncio.run(health_check())" || exit 1

# Команда запуска
CMD ["python", "-m", "app.main"]
