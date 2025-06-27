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

async def send_feature_announcements(context: CallbackContext) -> None:
    """Отправляет уведомления о новых фичах пользователям"""
    logger.info("🔔 Проверка новых фич для отправки уведомлений")
    
    from database import get_active_features_db, get_users_without_notification_db, mark_feature_sent_db
    
    # Получаем только продакшн фичи (не тестовые)
    active_features = get_active_features_db(include_test=False)
    
    for feature_id, feature_name, title, description, version, created_at, is_test in active_features:
        users_to_notify = get_users_without_notification_db(feature_id)
        
        if not users_to_notify:
            continue
            
        logger.info(f"📢 Отправка уведомлений о фиче '{feature_name}' для {len(users_to_notify)} пользователей")
        
        # Создаем клавиатуру для уведомления
        keyboard = [
            [InlineKeyboardButton("✨ Попробовать", callback_data=f"try_feature_{feature_id}")],
            [InlineKeyboardButton("ℹ️ Подробнее", callback_data=f"feature_info_{feature_id}")],
            [InlineKeyboardButton("❌ Закрыть", callback_data="close_notification")]
        ]
        
        version_text = f" (версия {version})" if version else ""
        message_text = f"🎉 **Новая функция: {title}**{version_text}\n\n{description}\n\n💡 Попробуйте прямо сейчас!"
        
        sent_count = 0
        for user_id in users_to_notify:
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=message_text,
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                mark_feature_sent_db(user_id, feature_id)
                sent_count += 1
                logger.info(f"✅ Уведомление о фиче отправлено пользователю {user_id}")
                
            except Exception as e:
                if "bot can't initiate conversation" in str(e) or "Forbidden" in str(e):
                    logger.warning(f"⚠️ Не удалось отправить уведомление пользователю {user_id}: заблокирован")
                    mark_feature_sent_db(user_id, feature_id)
                else:
                    logger.error(f"❌ Ошибка отправки уведомления пользователю {user_id}: {e}")
        
        logger.info(f"📊 Отправлено {sent_count} уведомлений о фиче '{feature_name}'")

async def send_test_feature_announcements(context: CallbackContext, test_user_id: int) -> None:
    """Отправляет тестовые уведомления о фичах только тестовому пользователю"""
    logger.info(f"🧪 Проверка тестовых фич для пользователя {test_user_id}")
    
    from database import get_active_features_db, get_users_without_notification_db, mark_feature_sent_db
    
    # Получаем только тестовые фичи
    all_features = get_active_features_db(include_test=True)
    test_features = [f for f in all_features if f[6] == 1]  # is_test = 1
    