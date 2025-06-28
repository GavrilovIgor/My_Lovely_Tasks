import os
import logging
import signal
import sys
from datetime import datetime, timedelta, timezone
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters, ConversationHandler, CallbackQueryHandler, ContextTypes, PreCheckoutQueryHandler
)
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY")
print(f"TOKEN: {'SET' if TOKEN else 'NOT SET'}")
print(f"YOOKASSA_SHOP_ID: {'SET' if YOOKASSA_SHOP_ID else 'NOT SET'}")
print(f"YOOKASSA_SECRET_KEY: {'SET' if YOOKASSA_SECRET_KEY else 'NOT SET'}")

DB_PATH = "data/tasks.db"
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# Состояния для ConversationHandler
ADDING_TASK = 1
DELETING_TASKS = 2

logs_dir = "logs"
if not os.path.exists(logs_dir):
    os.makedirs(logs_dir)
log_file = os.path.join(logs_dir, "bot.log")
logging.basicConfig(
    handlers=[logging.FileHandler(log_file), logging.StreamHandler()],
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from database import init_db
from handlers import (start, help_command, list_tasks, add, save_task, task_action, 
                     add_task_from_text, main_menu_handler, ask_delete_tasks, 
                     delete_tasks_by_numbers, send_reminder, SETTING_CUSTOM_REMINDER, 
                     save_custom_reminder, start_custom_reminder, support_developer, 
                     handle_donation_callback, pre_checkout_donation_handler, 
                     successful_donation_handler, stop_bot, admin_add_feature, admin_list_features, admin_deactivate_feature, test_feature_notifications, promote_test_feature)

from jobs import send_reminder_notification, send_feature_announcements, send_weekly_motivation

def get_seconds_until_next_monday_9am():
    """Возвращает количество секунд до следующего понедельника 09:00 МСК"""
    # Текущее время в МСК (UTC+3)
    now = datetime.now(timezone(timedelta(hours=3)))
    
    # Находим следующий понедельник
    days_ahead = 0 - now.weekday()  # 0 = понедельник
    if days_ahead <= 0:  # Если сегодня понедельник или позже
        days_ahead += 7  # Берём следующий понедельник
    
    # Создаём дату следующего понедельника в 09:00
    next_monday = now + timedelta(days=days_ahead)
    next_monday_9am = next_monday.replace(hour=9, minute=0, second=0, microsecond=0)
    
    # Если время уже прошло (например, сейчас понедельник 10:00), берём следующую неделю
    if next_monday_9am <= now:
        next_monday_9am += timedelta(days=7)
    
    # Возвращаем разность в секундах
    return (next_monday_9am - now).total_seconds()

menu_filter = (
    filters.Regex(r"^📋 Мои задачи$") |
    filters.Regex(r"^🧹 Удалить выполненные$") |
    filters.Regex(r"^🫶 Поддержи проект$")
) & ~filters.COMMAND

async def setup_commands(application):
    from telegram import BotCommand, BotCommandScopeDefault
    commands = [
        BotCommand("start", "Запустить бота"),
        BotCommand("help", "Помощь"),
        BotCommand("list", "Показать задачи"),
        BotCommand("stop", "Остановить бота"),
    ]
    await application.bot.set_my_commands(commands, scope=BotCommandScopeDefault())
    logger.info("Bot commands set up successfully")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Произошла ошибка при обработке обновления:", exc_info=context.error)
    error_message = f"Произошла ошибка: {context.error}"
    print(error_message)

def signal_handler(sig, frame):
    print("\nПолучен сигнал завершения. Закрываю бота...")
    logger.info("Бот завершает работу по сигналу")
    sys.exit(0)

def main():
    app = Application.builder().token(TOKEN).build()
    init_db()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("add", add)],
        states={
            ADDING_TASK: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_task)],
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)]
    )

    delete_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r"^🗑 Удалить задачи$"), ask_delete_tasks)],
        states={
            DELETING_TASKS: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_tasks_by_numbers)],
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)]
)

    from handlers import SETTING_CUSTOM_REMINDER, save_custom_reminder

    reminder_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_custom_reminder, pattern="^custom_reminder_")],  # ИСПРАВИТЬ
        states={
            SETTING_CUSTOM_REMINDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_custom_reminder)],
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)]
    )

    # Добавление обработчиков
    app.add_handler(reminder_conv_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("list", list_tasks))
    app.add_handler(CommandHandler("stop", stop_bot))

    # Новые команды для управления фичами
    app.add_handler(CommandHandler("add_feature", admin_add_feature))
    app.add_handler(CommandHandler("list_features", admin_list_features))
    app.add_handler(CommandHandler("deactivate_feature", admin_deactivate_feature))
    app.add_handler(CallbackQueryHandler(handle_donation_callback, pattern="donate|payment|cancel"))
    app.add_handler(CallbackQueryHandler(task_action))
    app.add_handler(conv_handler)
    app.add_handler(delete_conv_handler)
    app.add_handler(PreCheckoutQueryHandler(pre_checkout_donation_handler))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_donation_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~menu_filter, add_task_from_text))
    app.add_handler(MessageHandler(menu_filter, main_menu_handler))
    app.add_handler(CommandHandler("test_notifications", test_feature_notifications))
    app.add_handler(CommandHandler("promote_feature", promote_test_feature))
    job_queue = app.job_queue
    job_queue.run_repeating(send_reminder_notification, interval=60, first=10)
    job_queue.run_repeating(send_feature_announcements, interval=3600, first=30)
    # Еженедельная мотивационная рассылка каждый понедельник в 09:00 МСК
    first_monday_seconds = get_seconds_until_next_monday_9am()
    job_queue.run_repeating(
    send_weekly_motivation,
    interval=7*24*60*60,  # 7 дней в секундах (604800 секунд)
    first=first_monday_seconds)
    logger.info(f"Еженедельная рассылка запланирована. Первый запуск через {first_monday_seconds/3600:.1f} часов")
    app.job_queue.run_once(setup_commands, 1)
    logger.info("Бот запущен")
    print(f"Бот запущен! Данные сохраняются в {DB_PATH}. Логи в {logs_dir}")
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    app.add_error_handler(error_handler)
    app.run_polling()

if __name__ == "__main__":
    main()
