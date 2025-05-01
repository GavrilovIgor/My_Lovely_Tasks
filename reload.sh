#!/bin/bash

# Остановить контейнер (если он запущен)
docker stop my-lovely-tasks-container 2>/dev/null

# Удалить контейнер (если он существует)
docker rm my-lovely-tasks-container 2>/dev/null

# Очистить кэш Docker
docker system prune -f

# Пересобрать образ из текущей директории без использования кэша
docker build --no-cache -t my-lovely-tasks-container .

# Запустить новый контейнер в фоне
docker run -d --name my-lovely-tasks-container my-lovely-tasks-container