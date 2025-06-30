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
        
        version_text = f" (версия {version})" if version else ""
        # Заменяем подчеркивания на пробелы для красивого отображения
        display_title = title.replace("_", " ")
        display_description = description.replace("_", " ")
        message_text = f"🎉 Новая функция: {display_title}{version_text}\n\n{display_description}\n\n💡 Попробуйте прямо сейчас!"
        
        sent_count = 0
        for user_id in users_to_notify:
            try:
                # Простое уведомление без кнопок
                await context.bot.send_message(
                    chat_id=user_id,
                    text=message_text
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
    
    if not test_features:
        logger.info("🧪 Нет тестовых фич для отправки")
        return
    
    for feature_id, feature_name, title, description, version, created_at, is_test in test_features:
        users_to_notify = get_users_without_notification_db(feature_id, test_user_id)
        
        if not users_to_notify:
            logger.info(f"🧪 Пользователь {test_user_id} уже получал уведомление о фиче '{feature_name}'")
            continue
            
        logger.info(f"🧪 Отправка ТЕСТОВОГО уведомления о фиче '{feature_name}' пользователю {test_user_id}")
        
        version_text = f" (версия {version})" if version else ""
        # Заменяем подчеркивания на пробелы для красивого отображения
        display_title = title.replace("_", " ")
        display_description = description.replace("_", " ")
        message_text = f"🧪 ТЕСТ: {display_title}{version_text}\n\n{display_description}\n\n💡 Это тестовое уведомление - другие пользователи его не получат!"
        
        try:
            # Простое уведомление без кнопок
            await context.bot.send_message(
                chat_id=test_user_id,
                text=message_text
            )
            mark_feature_sent_db(test_user_id, feature_id)
            logger.info(f"✅ Тестовое уведомление о фиче отправлено пользователю {test_user_id}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки тестового уведомления пользователю {test_user_id}: {e}")
    
    logger.info(f"🧪 Завершена отправка тестовых уведомлений для пользователя {test_user_id}")

async def send_weekly_motivation(context: CallbackContext) -> None:
    """Отправляет еженедельное мотивационное сообщение всем пользователям"""
    logger.info("Запуск еженедельной мотивационной рассылки")
    
    # Получаем всех уникальных пользователей из базы
    from database import getconnection
    with getconnection() as conn:
        c = conn.cursor()
        c.execute("SELECT DISTINCT userid FROM tasks")
        user_ids = [row[0] for row in c.fetchall()]
    
    # Текст сообщения
    message_text = "🌟 Новая неделя — новые дела!\nНе держи все задачи в голове. Разгрузи её, выписав их сюда ✨"
    
    # Отправляем сообщение каждому пользователю
    sent_count = 0
    for user_id in user_ids:
        try:
            await context.bot.send_message(chat_id=user_id, text=message_text)
            sent_count += 1
            logger.info(f"Мотивационное сообщение отправлено пользователю {user_id}")
        except Exception as e:
            if "bot can't initiate conversation" in str(e) or "Forbidden" in str(e):
                logger.warning(f"Не удалось отправить сообщение пользователю {user_id}: заблокирован или удален чат")
            else:
                logger.error(f"Ошибка при отправке сообщения пользователю {user_id}: {e}")
    
    logger.info(f"Еженедельная рассылка завершена. Отправлено сообщений: {sent_count} из {len(user_ids)}")



    