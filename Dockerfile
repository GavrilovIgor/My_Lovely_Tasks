# Используем официальный Python-образ
FROM python:3.10

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /app

# Копируем все файлы проекта в контейнер
COPY . .

# Устанавливаем зависимости (если есть requirements.txt)
RUN pip install --no-cache-dir python-dotenv apscheduler python-telegram-bot

# Открываем порт (если бот работает с вебхуками, например)
# EXPOSE 8080

# Запускаем бота
CMD ["python", "bot.py"]
