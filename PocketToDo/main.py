import os
import logging
import signal
import sys
from datetime import datetime, timedelta, timezone
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters, ConversationHandler, CallbackQueryHandler, ContextTypes
)
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
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
from handlers import (
    start, help_command, list_tasks, add, save_task, 
    task_action, add_task_from_text, main_menu_handler,
    ask_delete_tasks, delete_tasks_by_numbers, send_reminder
)
from jobs import send_reminder_notification

menu_filter = (
    filters.Regex(r"^📋 Мои задачи$") |
    filters.Regex(r"^🧹 Удалить выполненные$")
) & ~filters.COMMAND

async def setup_commands(application):
    from telegram import BotCommand, BotCommandScopeDefault
    commands = [
        BotCommand("start", "Запуск бота"),
        BotCommand("help", "Что умеет бот?"),
        BotCommand("list", "Показать список задач")
    ]
    await application.bot.set_my_commands(commands, scope=BotCommandScopeDefault())
    logger.info("Команды бота настроены")

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
        states={ADDING_TASK: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_task)]},
        fallbacks=[]
    )
    delete_conv_handler = ConversationHandler(
        entry_points=[],
        states={DELETING_TASKS: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_tasks_by_numbers)]},
        fallbacks=[]
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("list", list_tasks))
    app.add_handler(CallbackQueryHandler(task_action))
    app.add_handler(conv_handler)
    app.add_handler(delete_conv_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~menu_filter, add_task_from_text))
    app.add_handler(MessageHandler(menu_filter, main_menu_handler))
    job_queue = app.job_queue
    job_queue.run_repeating(send_reminder_notification, interval=60, first=10)
    app.job_queue.run_once(setup_commands, 1)
    logger.info("Бот запущен")
    print(f"Бот запущен! Данные сохраняются в {DB_PATH}. Логи в {logs_dir}")
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    app.add_error_handler(error_handler)
    app.run_polling()

if __name__ == "__main__":
    main()