import logging
from typing import Any
from datetime import datetime, timedelta, timezone
from telegram.ext import CallbackContext
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from database import check_due_reminders, set_reminder

logger = logging.getLogger(__name__)

async def send_reminder_notification(context: CallbackContext) -> None:
    """
    Проверяет и отправляет уведомления о задачах с истекшим временем напоминания
    
    Args:
        context: Контекст бота
    """
    logger.info("Запущена проверка напоминаний")
    logger.info(f"Текущее время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    due_tasks = check_due_reminders()
    logger.info(f"Проверка напоминаний: найдено {len(due_tasks)} задач")
    
    if len(due_tasks) > 0:
        logger.info(f"Найдены задачи для напоминания: {due_tasks}")
    
    for task_id, user_id, text, done, reminder_time in due_tasks:
        # Отправляем напоминание напрямую
        try:
            # Создаем клавиатуру для напоминания с тремя вариантами
            keyboard = [
                [
                    InlineKeyboardButton(
                        text="✅ Выполнено / Отмена задачи",
                        callback_data=f"toggle_{task_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="⏰ Отложить на 1 час",
                        callback_data=f"snooze_reminder_{task_id}_60"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="📆 Отложить на завтра",
                        callback_data=f"snooze_reminder_{task_id}_tomorrow"
                    )
                ]
            ]
            
            # Сначала отправляем сообщение
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🔔 Напоминание: {text}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
            logger.info(f"Отправлено напоминание пользователю {user_id} о задаче {task_id}")
            
            # После успешной отправки помечаем как отправленное
            import sqlite3
            from database import DB_PATH
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("UPDATE tasks SET reminder_time = NULL WHERE id = ?", (task_id,))
            conn.commit()
            conn.close()
            logger.info(f"Напоминание помечено как отправленное: {task_id}")
        except Exception as e:
            logger.error(f"Ошибка при отправке напоминания: {e}")
