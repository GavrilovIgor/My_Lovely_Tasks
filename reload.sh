#!/bin/bash

# 1. Проверка наличия Dockerfile
if [ ! -f Dockerfile ]; then
    echo "Создаю Dockerfile..."
    cat > Dockerfile <<EOF
FROM python:3.10

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "bot.py"]
EOF
else
    echo "Dockerfile уже существует."
fi

# 2. Генерация requirements.txt, если его нет
if [ ! -f requirements.txt ]; then
    echo "Создаю requirements.txt..."
    pip freeze > requirements.txt
    echo "Проверь requirements.txt и оставь только нужные зависимости!"
else
    echo "requirements.txt уже существует."
fi

# 3. Сборка Docker-образа
echo "Собираю Docker-образ..."
docker build -t my-lovely-tasks .

# 4. Остановка и удаление старого контейнера, если он есть
if [ "$(docker ps -aq -f name=my-lovely-tasks-container)" ]; then
    echo "Удаляю старый контейнер..."
    docker stop my-lovely-tasks-container
    docker rm my-lovely-tasks-container
fi

# 5. Запуск нового контейнера с volume для базы и логов
# echo "Запускаю контейнер..."
# docker run -d --name my-lovely-tasks-container \
#   -v "$(pwd)/tasks.db:/app/tasks.db" \
#   -v "$(pwd)/bot.log:/app/bot.log" \
#   my-lovely-tasks

echo "Готово! Проверь логи командой: docker logs my-lovely-tasks-container"
