#!/bin/bash

# Остановить контейнер (если он запущен)
docker stop my-lovely-tasks-container 2>/dev/null

# Удалить контейнер (если он существует)
docker rm my-lovely-tasks-container 2>/dev/null

# Очистить кэш Docker
docker system prune -f

# Пересобрать образ из текущей директории
docker build --no-cache -t my-lovely-tasks-container .

# Запустить новый контейнер в фоне с монтированием папки данных
docker run -d --name my-lovely-tasks-container -v $(pwd)/PocketToDo/data:/app/data my-lovely-tasks-container

# Показать логи контейнера
docker logs -f my-lovely-tasks-container >> logs/bot.log 2>&1 &