# Используем официальный образ Python 3.12 с минимальным набором пакетов
FROM python:3.12-slim

# Устанавливаем рабочую директорию в контейнере
WORKDIR /app

# Копируем requirements.txt из корня проекта (внешняя директория)
# COPY ../requirements.txt .
COPY ../requirements.txt .


# Устанавливаем зависимости с кэшированием
RUN pip install -r requirements.txt --no-cache-dir

# Копируем только необходимые файлы бота
COPY telegram_bot/bot.py .
COPY telegram_bot/response_transformation.py .

# Создаем директорию для логов (если нужно)
RUN mkdir -p /app/logs

# Указываем переменные окружения (без значений - будут заданы при запуске)
# ENV TOKEN_TELEGRAM=
# ENV WEATHER_SERVICE_URL=http://weather_api:8001
# ENV AUTH_SERVICE_URL=http://auth_service:8002

# Запускаем бота
CMD ["python", "bot.py"]