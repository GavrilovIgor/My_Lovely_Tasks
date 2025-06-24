import logging
from datetime import datetime, timedelta, timezone
from telegram.ext import CallbackContext
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from database import check_due_reminders, set_reminder

logger = logging.getLogger(__name__)

async def send_reminder_notification(context: CallbackContext) -> None:
    """Проверяет и отправляет напоминания о задачах"""
    logger.info("Запущена проверка напоминаний")
    logger.info(f"Текущее время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    due_tasks = check_due_reminders()
    logger.info(f"Проверка напоминаний на {datetime.now(timezone(timedelta(hours=3)))}: найдено {len(due_tasks)} задач")
    
    if len(due_tasks) > 0:
        logger.info(f"Найдены задачи для напоминания: {due_tasks}")
        
        for task_id, user_id, text, done, reminder_time in due_tasks:
            try:
                # Правильные callback_data
                keyboard = [
                    [InlineKeyboardButton("✅ Задача выполнена", callback_data=f"toggle_{task_id}")],
                    [InlineKeyboardButton("🔕 Удалить напоминание", callback_data=f"delete_reminder_{task_id}")],
                    [InlineKeyboardButton("🔔 Отложить на 1 час", callback_data=f"snooze_reminder_{task_id}_60")],
                    [InlineKeyboardButton("🔔 Отложить на завтра в это же время", callback_data=f"snooze_reminder_{task_id}_tomorrow")],
                    [InlineKeyboardButton("🕐 Произвольное время", callback_data=f"custom_reminder_{task_id}")]
                ]
                
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"🔔 Напоминание: {text}",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                
                logger.info(f"Отправлено напоминание пользователю {user_id} о задаче {task_id}")
                
                # Удаляем напоминание после отправки
                set_reminder(task_id, None)
                
            except Exception as e:
                if "bot can't initiate conversation" in str(e) or "Forbidden" in str(e):
                    logger.warning(f"Не удалось отправить напоминание пользователю {user_id}, удаляем задачу {task_id}")
                    set_reminder(task_id, None)
                else:
                    logger.error(f"Ошибка при отправке напоминания: {e}")
