import sqlite3
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Tuple, Optional
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
    check_table_structure()  # Добавьте эту строку временно
    with get_connection() as conn:
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            text TEXT,
            done INTEGER DEFAULT 0,
            priority INTEGER DEFAULT 0,
            reminder_time TIMESTAMP DEFAULT NULL,
            reminder_sent INTEGER DEFAULT 0
        )""")
        
        c.execute("""CREATE TABLE IF NOT EXISTS donations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            payment_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        
        c.execute("""CREATE TABLE IF NOT EXISTS feature_announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            feature_name TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            version TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            is_test INTEGER DEFAULT 0
        )""")
        
        # Проверяем и добавляем недостающие колонки в feature_announcements
        c.execute("PRAGMA table_info(feature_announcements)")
        columns = [column[1] for column in c.fetchall()]
        
        if "is_test" not in columns:
            c.execute("ALTER TABLE feature_announcements ADD COLUMN is_test INTEGER DEFAULT 0")
            logger.info("Добавлена колонка 'is_test' в таблицу feature_announcements")
        
        conn.commit()

def add_task_db(user_id: int, text: str, priority: int = 0) -> int:
    logger.info(f"add_task_db called: user_id={user_id}, text='{text}', priority={priority}")
    from utils import extract_reminder_time, extract_priority, extract_categories

    # Извлекаем приоритет из текста задачи
    task_priority, text_without_priority = extract_priority(text)
    if task_priority > 0:
        priority = task_priority
        text = text_without_priority

    # Извлекаем категории и чистим текст от тегов
    categories = extract_categories(text)

    # Извлекаем время напоминания из текста задачи
    reminder_time, _ = extract_reminder_time(text)
    with get_connection() as conn:
        c = conn.cursor()
        if reminder_time:
            reminder_str = reminder_time.strftime("%Y-%m-%d %H:%M:%S")
            c.execute(
                "INSERT INTO tasks (user_id, text, done, priority, reminder_time) VALUES (?, ?, 0, ?, ?)",
                (user_id, text, priority, reminder_str),
            )
            task_id = c.lastrowid
            logger.info(f"Добавлена задача: id={task_id}, user_id={user_id}, text='{text}', priority={priority}, reminder_time={reminder_str}")
        else:
            c.execute(
                "INSERT INTO tasks (user_id, text, done, priority) VALUES (?, ?, 0, ?)",
                (user_id, text, priority),
            )
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

def add_donation_db(user_id: int, amount: int, payment_id: str = None) -> None:
    """Записывает информацию о поддержке в базу данных"""
    with get_connection() as conn:
        c = conn.cursor()
        # Создаем таблицу если её нет
        c.execute('''CREATE TABLE IF NOT EXISTS donations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            payment_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        c.execute('''INSERT INTO donations (user_id, amount, payment_id) 
                     VALUES (?, ?, ?)''', (user_id, amount, payment_id))
        conn.commit()
        logger.info(f"Donation recorded: user_id={user_id}, amount={amount}")

def get_user_donations_db(user_id: int) -> int:
    """Возвращает общую сумму поддержки от пользователя"""
    with get_connection() as conn:
        c = conn.cursor()
        c.execute('''SELECT COALESCE(SUM(amount), 0) FROM donations WHERE user_id = ?''', (user_id,))
        result = c.fetchone()
        return result[0] if result else 0

def get_total_donations_db() -> tuple:
    """Возвращает общую статистику поддержки (сумма, количество)"""
    with get_connection() as conn:
        c = conn.cursor()
        c.execute('''SELECT COALESCE(SUM(amount), 0), COUNT(*) FROM donations''')
        result = c.fetchone()
        return (result[0], result[1]) if result else (0, 0)

def add_feature_announcement_db(feature_name: str, title: str, description: str, version: str = None, is_test: bool = False) -> int:
    """Добавляет новое объявление о фиче"""
    with get_connection() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO feature_announcements (feature_name, title, description, version, is_test)
            VALUES (?, ?, ?, ?, ?)
        """, (feature_name, title, description, version, int(is_test)))
        feature_id = c.lastrowid
        conn.commit()
        test_flag = " (ТЕСТ)" if is_test else ""
        logger.info(f"Добавлено объявление о фиче: {feature_name} (ID: {feature_id}){test_flag}")
        return feature_id

def get_active_features_db(include_test: bool = False) -> List[Tuple]:
    """Получает активные объявления о фичах"""
    with get_connection() as conn:
        c = conn.cursor()
        if include_test:
            c.execute("""
                SELECT id, feature_name, title, description, version, created_at, is_test
                FROM feature_announcements 
                WHERE is_active = 1
                ORDER BY created_at DESC
            """)
        else:
            c.execute("""
                SELECT id, feature_name, title, description, version, created_at, is_test
                FROM feature_announcements 
                WHERE is_active = 1 AND is_test = 0
                ORDER BY created_at DESC
            """)
        return c.fetchall()

def get_users_without_notification_db(feature_id: int, test_user_id: int = None) -> List[int]:
    """Получает список пользователей, которые не получали уведомление о фиче"""
    with get_connection() as conn:
        c = conn.cursor()
        
        # Проверяем, является ли фича тестовой
        c.execute("SELECT is_test FROM feature_announcements WHERE id = ?", (feature_id,))
        result = c.fetchone()
        if not result:
            return []
        
        is_test = result[0]
        
        if is_test and test_user_id:
            # Для тестовых фич отправляем только тестовому пользователю
            c.execute("""
                SELECT ?
                WHERE ? NOT IN (
                    SELECT ufn.user_id
                    FROM user_feature_notifications ufn
                    WHERE ufn.feature_id = ?
                )
            """, (test_user_id, test_user_id, feature_id))
            result = c.fetchone()
            return [test_user_id] if result else []
        elif not is_test:
            # Для обычных фич отправляем всем пользователям
            c.execute("""
                SELECT DISTINCT t.user_id
                FROM tasks t
                WHERE t.user_id NOT IN (
                    SELECT ufn.user_id
                    FROM user_feature_notifications ufn
                    WHERE ufn.feature_id = ?
                )
            """, (feature_id,))
            return [row[0] for row in c.fetchall()]
        else:
            # Тестовая фича без указания тестового пользователя
            return []

def mark_feature_sent_db(user_id: int, feature_id: int) -> None:
    """Отмечает, что пользователь получил уведомление о фиче"""
    with get_connection() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT OR IGNORE INTO user_feature_notifications (user_id, feature_id)
            VALUES (?, ?)
        """, (user_id, feature_id))
        conn.commit()

def deactivate_feature_db(feature_id: int) -> None:
    """Деактивирует объявление о фиче (останавливает отправку уведомлений)"""
    with get_connection() as conn:
        c = conn.cursor()
        c.execute("UPDATE feature_announcements SET is_active = 0 WHERE id = ?", (feature_id,))
        conn.commit()
        logger.info(f"Фича {feature_id} деактивирована")

# Добавьте временно в database.py для проверки
def check_table_structure():
    with get_connection() as conn:
        c = conn.cursor()
        c.execute("PRAGMA table_info(tasks)")
        columns = c.fetchall()
        print("Структура таблицы tasks:")
        for column in columns:
            print(f"  {column[1]} ({column[2]})")

