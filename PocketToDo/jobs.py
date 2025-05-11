import logging
from typing import Any
from datetime import datetime
from telegram.ext import CallbackContext
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from database import check_due_reminders, set_reminder

logger = logging.getLogger(__name__)

async def test_notification(context: CallbackContext) -> None:
    """
    Отправляет тестовое уведомление для проверки работы планировщика
    
    Args:
        context: Контекст бота
    """
    logger.info("Выполняется тестовое напоминание")
    try:
        admin_id = context.bot_data.get("admin_id", context.bot.id)
        await context.bot.send_message(
            chat_id=admin_id,
            text="🔔 Тестовое напоминание работает!"
        )
        logger.info("Тестовое напоминание отправлено")
    except Exception as e:
        logger.error(f"Ошибка при отправке тестового напоминания: {e}")

async def send_reminder_notification(context: CallbackContext) -> None:
    """
    Проверяет и отправляет уведомления о задачах с истекшим временем напоминания
    
    Args:
        context: Контекст бота
    """
    logger.info("Запущена проверка напоминаний")
    due_tasks = check_due_reminders()
    logger.info(f"Проверка напоминаний: найдено {len(due_tasks)} задач")
    
    if len(due_tasks) > 0:
        logger.info(f"Найдены задачи для напоминания: {due_tasks}")
    
    for task_id, user_id, text, done, reminder_time in due_tasks:
        # Создаем клавиатуру для напоминания
        keyboard = [
            [
                InlineKeyboardButton(
                    text="✅ Выполнено",
                    callback_data=f"toggle_{task_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⏰ Отложить на 30 мин",
                    callback_data=f"snooze_reminder_{task_id}_30"
                )
            ]
        ]
        
        # Отправляем уведомление пользователю
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🔔 Напоминание: {text}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            logger.info(f"Отправлено напоминание пользователю {user_id} о задаче {task_id}")
            
            # Сбрасываем напоминание, чтобы оно не повторялось
            set_reminder(task_id, None)
        except Exception as e:
            logger.error(f"Ошибка при отправке напоминания: {e}")
