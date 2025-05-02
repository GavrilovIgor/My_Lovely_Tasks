import os
import re
import sqlite3
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters, ConversationHandler)
from apscheduler.schedulers.background import BackgroundScheduler

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
DB_PATH = "tasks.db"
ADDING_TASK = 1
DELETING_TASKS = 2

import logging
import os

# Получаем абсолютный путь к log-файлу в текущей директории проекта
LOG_PATH = os.path.join(os.path.dirname(__file__), "bot.log")

logging.basicConfig(
    filename=LOG_PATH,
    filemode="a",
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Работа с БД ---

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            text TEXT,
            done INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def add_task_db(user_id, text):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO tasks (user_id, text, done) VALUES (?, ?, 0)", (user_id, text))
    conn.commit()
    conn.close()
    logger.info(f"Добавлена задача: user_id={user_id}, text='{text}'")

def get_tasks_db(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, text, done FROM tasks WHERE user_id = ? ORDER BY id", (user_id,))
    tasks = c.fetchall()
    conn.close()
    return tasks

def get_main_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["➕ Добавить задачу", "📋 Мои задачи"],
            ["🗑 Удалить задачу", "🧹 Удалить выполненные"]
        ], 
        resize_keyboard=True
    )

# В функции toggle_task_db
def toggle_task_db(task_id, user_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "UPDATE tasks SET done = NOT done WHERE id = ? AND user_id = ?",
            (task_id, user_id)
        )
        conn.commit()
        updated = c.rowcount > 0  # Проверяем, была ли обновлена задача
        conn.close()
        logger.info(f"Переключен статус задачи id={task_id} (user_id={user_id})")
        return updated
    except Exception as e:
        logger.error(f"Ошибка переключения задачи: {e}")
        return False
    finally:
        if conn:
            conn.close()

def delete_completed_tasks():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM tasks WHERE done = 1")
    conn.commit()
    conn.close()
    print("Выполненные задачи удалены из базы.")

def delete_completed_tasks_for_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM tasks WHERE user_id = ? AND done = 1", (user_id,))
    conn.commit()
    conn.close()


async def main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text
        if text == "➕ Добавить задачу":
            return await add(update, context)
        elif text == "📋 Мои задачи":
            await list_tasks(update, context)
            return ConversationHandler.END
        elif text == "🗑 Удалить задачу":  # Добавлено!
            return await ask_delete_tasks(update, context)
        elif text == "🧹 Удалить выполненные":
            user_id = update.message.from_user.id
            delete_completed_tasks_for_user(user_id)
            await update.message.reply_text("Выполненные задачи удалены.", reply_markup=get_main_keyboard())
            await list_tasks(update, context)
            return ConversationHandler.END
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return ConversationHandler.END

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "😺 Привет, организованный человек! Я – твой уютный помощник для задач!\n\n"
        "📝 Я создан, чтобы твоё \"Избранное\" не превращалось в свалку списков дел, а жизнь стала проще! \n\n"
        "✨ Что я умею:\n"
        "- Добавлять задачи (просто напиши мне что нужно сделать!)\n"
        "- Отмечать выполненные (приятное чувство, когда вычёркиваешь дела ✅)\n"
        "- Удалять ненужное (чистота – залог продуктивности! 😊)\n\n"
        "🚀 Начнём вместе делать твои дела? Используй кнопки меню или просто напиши мне задачу!",
        reply_markup=get_main_keyboard()
    )

def delete_task_db(task_id, user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM tasks WHERE id = ? AND user_id = ?", (task_id, user_id))
    conn.commit()
    conn.close()
    logger.info(f"Удалена задача id={task_id} для user_id={user_id}")
    
# --- Telegram-бот ---

def get_task_list_markup(user_id):
    tasks = get_tasks_db(user_id)
    keyboard = []

    # Статистика
    total = len(tasks)
    done_count = sum(1 for task in tasks if task[2])
    keyboard.append([
        InlineKeyboardButton(
            text=f"✅ {done_count}/{total} выполнено",
            callback_data="toggle_all"
        )
    ])
    keyboard.append([
        InlineKeyboardButton(text="▬▬▬▬▬▬▬▬▬▬", callback_data="divider")
    ])

    for i, (task_id, text, done) in enumerate(tasks, 1):
        if done:
            task_text = f"{i}. ✅ {text}"
        else:
            task_text = f"{i}. ☐ {text}"
        keyboard.append([
            InlineKeyboardButton(
                text=task_text,
                callback_data=f"toggle_{task_id}",
            )
        ])

    return InlineKeyboardMarkup(keyboard) if keyboard else None

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите задачи с новой строки или через точку с запятой (например: Задача 1; Задача 2):")
    return ADDING_TASK

async def save_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    input_text = update.message.text.strip()
    
    # Проверяем, нажал ли пользователь кнопку отмены
    if input_text == "❌ Отмена":
        await update.message.reply_text(
            "Добавление отменено.",
            reply_markup=get_main_keyboard()
        )
        return ConversationHandler.END
    
    # Список текстов кнопок, которые не должны добавляться как задачи
    menu_buttons = ["➕ Добавить задачу", "📋 Мои задачи", "🗑 Удалить задачу", "🧹 Удалить выполненные"]
    
    if not input_text:
        await update.message.reply_text("Пустой ввод. Попробуйте снова.")
        return ConversationHandler.END
    
    # Проверяем, не является ли ввод текстом кнопки меню
    if input_text in menu_buttons:
        # Если это кнопка меню, обрабатываем её как нажатие кнопки
        await main_menu_handler(update, context)
        return ConversationHandler.END
    
    tasks_list = [task.strip() for task in re.split(r';|\n', input_text) if task.strip()]
    added_count = 0
    
    for task_text in tasks_list:
        add_task_db(user_id, task_text)
        added_count += 1
    
    await update.message.reply_text("✅ Задачи добавлены!", reply_markup=get_main_keyboard())
    return ConversationHandler.END

async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    tasks = get_tasks_db(user_id)
    
    if not tasks:
        await update.message.reply_text("У вас пока нет задач 🙂")
        return

    task_texts = [
        f"{i+1}. <s>{text}</s>" if done else f"{i+1}. {text}"
        for i, (task_id, text, done) in enumerate(tasks)
]
    text_result = "Ваши задачи:\n" + "\n".join(task_texts)

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text=text_result,
            reply_markup=get_task_list_markup(user_id),
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(
            text_result,
            reply_markup=get_task_list_markup(user_id),
            parse_mode="HTML"
        )

def toggle_all_tasks_db(user_id, set_done: bool):
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # Явное преобразование bool в int
        c.execute("UPDATE tasks SET done = ? WHERE user_id = ?", (int(set_done), user_id))
        conn.commit()
        logger.info(f"Успешно обновлено {c.rowcount} задач")
    except Exception as e:
        logger.error(f"Ошибка массового обновления: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

async def task_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data

    # Массовое переключение
    if data == "toggle_all":
        tasks = get_tasks_db(user_id)
        if not tasks:
            await query.answer("Нет задач для изменения")
            return
        all_done = all(task[2] for task in tasks)
        new_status = not all_done
        try:
            toggle_all_tasks_db(user_id, new_status)
            await query.answer(f"Все задачи {'выполнены' if new_status else 'сброшены'}!")
            await list_tasks(update, context)
        except Exception as e:
            await query.answer("Ошибка обновления. Попробуйте снова.")
            logger.error(f"Ошибка toggle_all: {e}")
        return

    # Переключение одной задачи
    elif data.startswith("toggle_"):
        task_id = int(data.split("_")[1])
        success = toggle_task_db(task_id, user_id)
        if success:
            await query.answer("✅ Статус изменён")
        else:
            await query.answer("❌ Задача не найдена")
        await list_tasks(update, context)
        return

    # Игнорируем другие callback_data
    await query.answer()


async def ask_delete_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Создаем клавиатуру с кнопкой отмены
    cancel_keyboard = ReplyKeyboardMarkup(
        [["❌ Отмена"]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await update.message.reply_text(
        "Введите номера задач для удаления через запятую или диапазон (например: 1,3,5-7):",
        reply_markup=cancel_keyboard
    )
    return DELETING_TASKS

async def add_task_from_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text.strip()
    
    # Список текстов кнопок, которые не должны добавляться как задачи
    menu_buttons = ["➕ Добавить задачу", "📋 Мои задачи", "🗑 Удалить задачу", "🧹 Удалить выполненные"]
    
    if not text or text.startswith('/'):
        return  # Игнорируем пустые сообщения и команды
    
    # Проверяем, не является ли ввод текстом кнопки меню
    if text in menu_buttons:
        return  # Игнорируем тексты кнопок меню
    
    # Разделяем по ; или по переводу строки
    tasks_list = [task.strip() for task in re.split(r';|\n', text) if task.strip()]
    added_count = 0
    for task_text in tasks_list:
        add_task_db(user_id, task_text)
        added_count += 1
    await update.message.reply_text(
        "✅ Задачи добавлены!" if added_count > 1 else f"✅ Задача добавлена: {tasks_list[0]}",
        reply_markup=get_main_keyboard()
    )
    logger.info(f"Добавлены задачи через универсальный обработчик: user_id={user_id}, tasks={tasks_list}")

import re

async def ask_add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Создаем клавиатуру с кнопкой отмены
    cancel_keyboard = ReplyKeyboardMarkup(
        [["❌ Отмена"]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await update.message.reply_text(
        "Введите задачи через точку с запятой или с новой строки:",
        reply_markup=cancel_keyboard
    )
    return ADDING_TASK

async def delete_tasks_by_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    input_text = update.message.text.strip()
    
    # Проверяем, нажал ли пользователь кнопку отмены
    if input_text == "❌ Отмена":
        await update.message.reply_text(
            "Удаление отменено.",
            reply_markup=get_main_keyboard()
        )
        return ConversationHandler.END
    
    # Список текстов кнопок, которые не должны обрабатываться как номера задач
    menu_buttons = ["➕ Добавить задачу", "📋 Мои задачи", "🗑 Удалить задачу", "🧹 Удалить выполненные"]
    
    if input_text in menu_buttons:
        # Если это кнопка меню, обрабатываем её как нажатие кнопки
        await main_menu_handler(update, context)
        return ConversationHandler.END
    
    input_text = input_text.replace(' ', '')
    tasks = get_tasks_db(user_id)
    to_delete = set()

    # Разбиваем по запятой
    for part in input_text.split(','):
        if '-' in part:
            # Диапазон, например 2-5
            try:
                start, end = map(int, part.split('-'))
                for n in range(start, end + 1):
                    if 1 <= n <= len(tasks):
                        to_delete.add(tasks[n-1][0])  # task_id
            except Exception:
                continue
        else:
            # Одиночный номер
            if part.isdigit():
                n = int(part)
                if 1 <= n <= len(tasks):
                    to_delete.add(tasks[n-1][0])  # task_id

    if not to_delete:
        await update.message.reply_text(
            "Нет подходящих задач для удаления. Введите номера через запятую или диапазон, например: 1,3,5-7",
            reply_markup=get_main_keyboard()
        )
        return ConversationHandler.END

    for task_id in to_delete:
        delete_task_db(task_id, user_id)

    await update.message.reply_text("Выбранные задачи удалены.", reply_markup=get_main_keyboard())
    await list_tasks(update, context)
    return ConversationHandler.END

    for task_id in to_delete:
        delete_task_db(task_id, user_id)

    await update.message.reply_text("Выбранные задачи удалены.", reply_markup=get_main_keyboard())
    await list_tasks(update, context)
    return ConversationHandler.END

menu_filter = (
    filters.Regex(r"^➕ Добавить задачу$") |
    filters.Regex(r"^📋 Мои задачи$") |
    filters.Regex(r"^🗑 Удалить задачу$") |
    filters.Regex(r"^🧹 Удалить выполненные$")
) & ~filters.COMMAND

def main():
    # 1. Инициализация базы данных
    init_db()

    # 2. Создание приложения Telegram-бота
    app = ApplicationBuilder().token(TOKEN).build()

    # 3. Добавление ConversationHandler для добавления задач
    conv_handler = ConversationHandler(
    entry_points=[
        CommandHandler("add", add),
        MessageHandler(filters.Regex(r"^➕ Добавить задачу$"), add),
        MessageHandler(filters.Regex(r"^🗑 Удалить задачу$"), ask_delete_tasks)
    ],
    states={
        ADDING_TASK: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_task)],
        DELETING_TASKS: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_tasks_by_numbers)]
    },
    fallbacks=[]
)

    # 4. Добавление всех обработчиков команд
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list", list_tasks))
    app.add_handler(CallbackQueryHandler(task_action))
    app.add_handler(MessageHandler(menu_filter, main_menu_handler))
    # Добавьте этот обработчик последним
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & ~menu_filter,
        add_task_from_text
    ))

    # 5. Настройка и запуск планировщика
    from apscheduler.schedulers.background import BackgroundScheduler  # если не импортировал выше
    scheduler = BackgroundScheduler()
    scheduler.add_job(delete_completed_tasks, 'cron', hour=23, minute=59)
    scheduler.start()
    print("Планировщик запущен: задачи будут очищаться в 23:59.")

    # 6. Запуск бота
    print("Бот запущен! Данные сохраняются в tasks.db.")
    app.run_polling()

if __name__ == "__main__":
    main()