# Используем официальный Python-образ
FROM python:3.10-slim

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /app

# Обновление pip
RUN pip install --upgrade pip

# Создаем директорию для данных
RUN mkdir -p /app/data

# Копируем файл с зависимостями
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код из папки PocketToDo в контейнер
COPY PocketToDo/ /app/

# Запускаем бота (предполагается, что точка входа - main.py)
CMD ["python", "main.py"]
