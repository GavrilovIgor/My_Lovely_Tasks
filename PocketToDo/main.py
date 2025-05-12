import os
import logging
import signal
import sys
from datetime import datetime
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

# Создаем директорию logs, если она не существует
logs_dir = "/logs"
if not os.path.exists(logs_dir):
    os.makedirs(logs_dir)

# Настройка логирования
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

# Фильтр для кнопок главного меню
menu_filter = (
    filters.Regex(r"^📋 Мои задачи$") |
    filters.Regex(r"^🧹 Удалить выполненные$")
) & ~filters.COMMAND

async def setup_commands(application):
    """Настройка команд бота в меню"""
    from telegram import BotCommand, BotCommandScopeDefault
    
    commands = [
        BotCommand("start", "Перезапустить бота / обновить меню"),
        BotCommand("list", "Показать список задач"),
        BotCommand("add", "Добавить новую задачу")
    ]
    
    await application.bot.set_my_commands(
        commands,
        scope=BotCommandScopeDefault()
    )
    logger.info("Команды бота настроены")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Логирует ошибки и отправляет сообщение разработчику."""
    # Записываем ошибку в лог
    logger.error("Произошла ошибка при обработке обновления:", exc_info=context.error)
    
    # Получаем информацию об ошибке
    error_message = f"Произошла ошибка: {context.error}"
    
    # Выводим в консоль для отладки
    print(error_message)
    
    # Можно также отправить себе сообщение с ошибкой
    # await context.bot.send_message(chat_id=ТВОЙ_ID, text=error_message)

def signal_handler(sig, frame):
    """Корректно завершает работу бота при получении сигнала завершения."""
    print("\nПолучен сигнал завершения. Закрываю бота...")
    logger.info("Бот завершает работу по сигналу")
    # Здесь можно добавить код для закрытия соединений
    sys.exit(0)

def main():
    """Основная функция запуска бота"""
    # Создание приложения
    app = Application.builder().token(TOKEN).build()
    
    # Инициализация базы данных
    init_db()
    
    # Настройка обработчиков
    
    # ConversationHandler для добавления задач
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("add", add)],
        states={
            ADDING_TASK: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_task)]
        },
        fallbacks=[]
    )
    
    # ConversationHandler для удаления задач
    delete_conv_handler = ConversationHandler(
        entry_points=[],
        states={
            DELETING_TASKS: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_tasks_by_numbers)]
        },
        fallbacks=[]
    )
    
    # Основные команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("list", list_tasks))
    
    # Обработчики взаимодействия
    app.add_handler(CallbackQueryHandler(task_action))
    app.add_handler(conv_handler)
    app.add_handler(delete_conv_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~menu_filter, add_task_from_text))
    app.add_handler(MessageHandler(menu_filter, main_menu_handler))
    
    # Настройка планировщика задач
    job_queue = app.job_queue
    # job_queue.run_once(test_notification, 10)  # Закомментировано, так как функция отсутствует
    job_queue.run_repeating(send_reminder_notification, interval=15, first=5)

    
    # Настройка команд в меню бота
    app.job_queue.run_once(setup_commands, 1)
    
    logger.info("Бот запущен")
    print(f"Бот запущен! Данные сохраняются в {DB_PATH}. Логи в {logs_dir}")
    
    # Регистрируем обработчики сигналов
    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # kill

    # Запуск бота
    app.add_error_handler(error_handler)
    app.run_polling()

if __name__ == "__main__":
    main()
