import sqlite3
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Tuple, Optional, Any, Dict, Union
from contextlib import contextmanager

logger = logging.getLogger(__name__)

DB_PATH = "data/tasks.db"

@contextmanager
def get_connection():
    """Контекстный менеджер для соединения с БД"""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        yield conn
    except Exception as e:
        logger.error(f"Ошибка при работе с БД: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

def init_db() -> None:
    """Инициализация базы данных"""
    with get_connection() as conn:
        c = conn.cursor()
        c.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            text TEXT,
            done INTEGER DEFAULT 0,
            priority INTEGER DEFAULT 0,
            reminder_time TIMESTAMP DEFAULT NULL,
            reminder_sent INTEGER DEFAULT 0
        )
    """)
        # Добавить миграцию для существующей БД:
        c.execute("PRAGMA table_info(tasks)")
        columns = [column[1] for column in c.fetchall()]
        if 'reminder_sent' not in columns:
            c.execute("ALTER TABLE tasks ADD COLUMN reminder_sent INTEGER DEFAULT 0")
            logger.info("Добавлена колонка reminder_sent в таблицу tasks")

        
        # Проверяем, существует ли колонка priority
        c.execute("PRAGMA table_info(tasks)")
        columns = [column[1] for column in c.fetchall()]
        
        # Если колонки priority нет, добавляем ее
        if 'priority' not in columns:
            c.execute("ALTER TABLE tasks ADD COLUMN priority INTEGER DEFAULT 0")
            logger.info("Добавлена колонка priority в таблицу tasks")
        
        # Если колонки reminder_time нет, добавляем ее
        if 'reminder_time' not in columns:
            c.execute("ALTER TABLE tasks ADD COLUMN reminder_time TIMESTAMP DEFAULT NULL")
            logger.info("Добавлена колонка reminder_time в таблицу tasks")
        
        conn.commit()

def add_task_db(user_id: int, text: str, priority: int = 0) -> int:
    """Добавление новой задачи в БД"""
    from utils import extract_reminder_time, extract_priority  # Импорт здесь для избежания циклических импортов
    
    # Извлекаем приоритет из текста задачи
    task_priority, text_without_priority = extract_priority(text)
    
    # Если приоритет указан в тексте, используем его, иначе используем переданный параметр
    if task_priority > 0:
        priority = task_priority
        text = text_without_priority
    
    # Извлекаем время напоминания из текста задачи
    reminder_time, clean_text = extract_reminder_time(text)
    
    with get_connection() as conn:
        c = conn.cursor()
        
        if reminder_time:
            # Если есть напоминание, сохраняем его
            reminder_str = reminder_time.strftime('%Y-%m-%d %H:%M:%S')
            c.execute("""
                INSERT INTO tasks (user_id, text, done, priority, reminder_time) 
                VALUES (?, ?, 0, ?, ?)
            """, (user_id, clean_text, priority, reminder_str))
            task_id = c.lastrowid
            logger.info(f"Добавлена задача с напоминанием: id={task_id}, user_id={user_id}, text='{clean_text}', priority={priority}, reminder={reminder_str}")
        else:
            # Если напоминания нет, сохраняем без него
            c.execute("""
                INSERT INTO tasks (user_id, text, done, priority) 
                VALUES (?, ?, 0, ?)
            """, (user_id, text, priority))
            task_id = c.lastrowid
            logger.info(f"Добавлена задача: id={task_id}, user_id={user_id}, text='{text}', priority={priority}")
        
        conn.commit()
        return task_id

def update_task_priority(task_id: int, priority: int) -> None:
    """Обновление приоритета задачи"""
    with get_connection() as conn:
        c = conn.cursor()
        c.execute("UPDATE tasks SET priority = ? WHERE id = ?", (priority, task_id))
        conn.commit()
        logger.info(f"Обновлен приоритет задачи id={task_id} на {priority}")

def get_tasks_db(user_id: int, only_open: bool = False) -> List[Tuple]:
    """Получение списка задач пользователя"""
    with get_connection() as conn:
        c = conn.cursor()
        if only_open:
            c.execute("""
                SELECT id, text, done, priority, reminder_time 
                FROM tasks 
                WHERE user_id = ? AND done = 0 
                ORDER BY priority DESC, id ASC
            """, (user_id,))
        else:
            c.execute("""
                SELECT id, text, done, priority, reminder_time 
                FROM tasks 
                WHERE user_id = ? 
                ORDER BY priority DESC, id ASC
            """, (user_id,))
        tasks = c.fetchall()
        return tasks

def toggle_task_db(task_id: int, user_id: int) -> bool:
    """Переключение статуса задачи"""
    try:
        with get_connection() as conn:
            c = conn.cursor()
            c.execute(
                "UPDATE tasks SET done = NOT done WHERE id = ? AND user_id = ?",
                (task_id, user_id)
            )
            conn.commit()
            updated = c.rowcount > 0  # Проверяем, была ли обновлена задача
            logger.info(f"Переключен статус задачи id={task_id} (user_id={user_id})")
            return updated
    except Exception as e:
        logger.error(f"Ошибка переключения задачи: {e}")
        return False

def set_reminder(task_id: int, reminder_time: Optional[datetime]) -> None:
    """Установка времени напоминания для задачи"""
    with get_connection() as conn:
        c = conn.cursor()
        c.execute("UPDATE tasks SET reminder_time = ? WHERE id = ?", 
                (reminder_time.strftime('%Y-%m-%d %H:%M:%S') if reminder_time else None, task_id))
        conn.commit()
        logger.info(f"Установлено напоминание для задачи id={task_id} на {reminder_time}")

def get_tasks_with_reminders(user_id: int) -> List[Tuple]:
    """Получение списка задач с напоминаниями для пользователя"""
    with get_connection() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT id, text, done, priority, reminder_time 
            FROM tasks 
            WHERE user_id = ? AND reminder_time IS NOT NULL
            ORDER BY reminder_time
        """, (user_id,))
        tasks = c.fetchall()
        return tasks

def check_due_reminders() -> List[Tuple]:
    """Проверка задач с истекшим временем напоминания"""
    with get_connection() as conn:
        c = conn.cursor()
        now = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=3)))  
        # МСК
        now_str = now.strftime('%Y-%m-%d %H:%M:%S')
        # Выводим все напоминания для отладки
        c.execute("SELECT id, user_id, text, reminder_time FROM tasks WHERE reminder_time IS NOT NULL")
        all_reminders = c.fetchall()
        logger.info(f"Все напоминания в системе: {all_reminders}")

        # Исключаем напоминания, которые уже были отправлены (содержат метку "_sent")
        c.execute("""
            SELECT id, user_id, text, done, reminder_time 
            FROM tasks 
            WHERE reminder_time IS NOT NULL 
            AND DATETIME(reminder_time) <= DATETIME(?) 
            AND done = 0
            AND reminder_time NOT LIKE '%\\_sent' ESCAPE '\\'
        """, (now_str,))

        due_tasks = c.fetchall()
        
        logger.info(f"Проверка напоминаний на {now}: найдено {len(due_tasks)} задач")
        if due_tasks:
            logger.info(f"Задачи с истекшим временем: {due_tasks}")
        return due_tasks

def toggle_task_status_db(task_id: int, new_status: Optional[int] = None) -> bool:
    """Изменение статуса задачи"""
    try:
        with get_connection() as conn:
            c = conn.cursor()
            
            if new_status is not None:
                # Устанавливаем конкретный статус
                c.execute("UPDATE tasks SET done = ? WHERE id = ?", (new_status, task_id))
            else:
                # Переключаем текущий статус
                c.execute("UPDATE tasks SET done = NOT done WHERE id = ?", (task_id,))
            
            conn.commit()
            rows_affected = c.rowcount
            logger.info(f"Изменен статус задачи id={task_id}, затронуто строк: {rows_affected}")
            return rows_affected > 0
    except Exception as e:
        logger.error(f"Ошибка при изменении статуса задачи {task_id}: {e}")
        return False

def delete_completed_tasks_for_user(user_id: int) -> None:
    """Удаление выполненных задач пользователя"""
    with get_connection() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM tasks WHERE user_id = ? AND done = 1", (user_id,))
        conn.commit()
        logger.info(f"Удалены выполненные задачи пользователя {user_id}")

def delete_task_db(task_id: int, user_id: int) -> None:
    """Удаление задачи"""
    with get_connection() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM tasks WHERE id = ? AND user_id = ?", (task_id, user_id))
        conn.commit()
        logger.info(f"Удалена задача id={task_id} для user_id={user_id}")

def toggle_all_tasks_db(user_id: int, set_done: bool) -> None:
    """Изменение статуса всех задач пользователя"""
    try:
        with get_connection() as conn:
            c = conn.cursor()
            # Явное преобразование bool в int
            c.execute("UPDATE tasks SET done = ? WHERE user_id = ?", (int(set_done), user_id))
            conn.commit()
            logger.info(f"Успешно обновлено {c.rowcount} задач")
    except Exception as e:
        logger.error(f"Ошибка массового обновления: {e}")
