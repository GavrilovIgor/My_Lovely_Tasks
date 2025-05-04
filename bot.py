import os
import re
import sqlite3
from telegram import BotCommand, BotCommandScopeDefault
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters, ConversationHandler)

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
            done INTEGER DEFAULT 0,
            priority INTEGER DEFAULT 0
        )
    """)
    
    # Проверяем, существует ли колонка priority
    c.execute("PRAGMA table_info(tasks)")
    columns = [column[1] for column in c.fetchall()]
    
    # Если колонки priority нет, добавляем ее
    if 'priority' not in columns:
        c.execute("ALTER TABLE tasks ADD COLUMN priority INTEGER DEFAULT 0")
        print("Добавлена колонка priority в таблицу tasks")
    
    conn.commit()
    conn.close()

def add_task_db(user_id, text, priority=0):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO tasks (user_id, text, done, priority) VALUES (?, ?, 0, ?)", (user_id, text, priority))
    conn.commit()
    conn.close()
    logger.info(f"Добавлена задача: user_id={user_id}, text='{text}'")

def update_task_priority(task_id, priority):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE tasks SET priority = ? WHERE id = ?", (priority, task_id))
    conn.commit()
    conn.close()

def get_tasks_db(user_id, only_open=False):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if only_open:
        c.execute("SELECT id, text, done, priority FROM tasks WHERE user_id = ? AND done = 0 ORDER BY priority DESC, id", (user_id,))
    else:
        c.execute("SELECT id, text, done, priority FROM tasks WHERE user_id = ? ORDER BY priority DESC, id", (user_id,))
    tasks = c.fetchall()
    conn.close()
    return tasks

def get_main_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["📋 Мои задачи"],
            ["🧹 Удалить выполненные"]
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

def toggle_task_status_db(task_id, new_status=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    if new_status is not None:
        # Устанавливаем конкретный статус
        c.execute("UPDATE tasks SET done = ? WHERE id = ?", (new_status, task_id))
    else:
        # Переключаем текущий статус
        c.execute("UPDATE tasks SET done = NOT done WHERE id = ?", (task_id,))
    
    conn.commit()
    conn.close()
    logger.info(f"Изменен статус задачи id={task_id}")

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

async def setup_commands(application):
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

async def main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text
        if text == "➕ Добавить задачу":
            return await add(update, context)
        elif text == "📋 Мои задачи":
            # Добавляем логирование для отладки
            logger.info(f"Нажата кнопка 'Мои задачи' пользователем {update.effective_user.id}")
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
        logger.error(f"Ошибка в main_menu_handler: {e}")
        # Отправляем сообщение об ошибке пользователю
        await update.message.reply_text("Произошла ошибка. Попробуйте еще раз.")
        return ConversationHandler.END

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "😺 Привет, организованный человек! Я – твой карманный помощник для задач!\n\n"
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
    tasks = get_tasks_db(user_id, only_open=False)
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
        InlineKeyboardButton(
            text="🔝 Определить приоритет",
            callback_data="priority_mode"
        )
    ])
    
    keyboard.append([
        InlineKeyboardButton(text="▬▬▬▬▬▬▬▬▬▬", callback_data="divider")
    ])

    # Словарь эмодзи для приоритетов
    priority_emoji = {
        3: "🔴", # Высокий
        2: "🟡", # Средний
        1: "🔵"  # Низкий
    }

    for task_id, text, done, priority in tasks:
        # Формируем статус задачи
        status = "✅" if done else "☐"
        
        # Формируем текст задачи с новой структурой
        task_text = f"{status} "
        
        # Добавляем приоритет только если он установлен (не 0)
        if priority > 0:
            priority_icon = priority_emoji.get(priority, "")
            task_text += f"{priority_icon} "
        
        # Добавляем текст задачи
        task_text += text
        
        keyboard.append([
            InlineKeyboardButton(
                text=task_text,
                callback_data=f"toggle_{task_id}",
            )
        ])

    return InlineKeyboardMarkup(keyboard) if keyboard else None

async def show_priority_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    tasks = get_tasks_db(user_id, only_open=False)
    
    keyboard = []
    keyboard.append([
        InlineKeyboardButton(
            text="Выберите задачу для изменения приоритета:",
            callback_data="divider"
        )
    ])
    
    for i, (task_id, text, done, priority) in enumerate(tasks, 1):
        # Сокращаем текст, если он слишком длинный
        short_text = text[:30] + "..." if len(text) > 30 else text
        task_text = f"{i}. {short_text}"
        
        keyboard.append([
            InlineKeyboardButton(
                text=task_text,
                callback_data=f"set_priority_{task_id}"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton(
            text="↩️ Назад",
            callback_data="back_to_list"
        )
    ])
    
    await query.edit_message_text(
        text="🔄 Режим изменения приоритетов",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_priority_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Извлекаем ID задачи из callback_data
    task_id = int(query.data.split('_')[2])
    
    keyboard = [
        [
            InlineKeyboardButton(
                text="🔴 Высокий",
                callback_data=f"priority_{task_id}_3"
            )
        ],
        [
            InlineKeyboardButton(
                text="🟡 Средний",
                callback_data=f"priority_{task_id}_2"
            )
        ],
        [
            InlineKeyboardButton(
                text="🔵 Низкий",
                callback_data=f"priority_{task_id}_1"
            )
        ],
        [
            InlineKeyboardButton(
                text="↩️ Назад",
                callback_data="priority_mode"
            )
        ]
    ]
    
    await query.edit_message_text(
        text="Выберите приоритет для задачи:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def set_task_priority(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Извлекаем ID задачи и приоритет из callback_data
    parts = query.data.split('_')
    task_id = int(parts[1])
    priority = int(parts[2])
    
    # Обновляем приоритет в базе данных
    update_task_priority(task_id, priority)
    
    # Возвращаемся к меню расстановки приоритетов вместо списка задач
    await show_priority_menu(update, context)

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Вводите задачи с новой строки или через точку с запятой (например: Задача 1\nЗадача 2\n или\nЗадача 1; Задача 2)")
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
    menu_buttons = ["📋 Мои задачи", "🧹 Удалить выполненные", "❌ Отмена"]
    
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
    
    # Сразу показываем список задач
    await list_tasks(update, context)
    
    return ConversationHandler.END

async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    tasks = get_tasks_db(user_id, only_open=False)
    
    # Создаем клавиатуру заранее, чтобы проверить ее
    keyboard_markup = get_task_list_markup(user_id)
    
    if not tasks:
        if update.callback_query:
            await update.callback_query.answer("У вас пока нет задач 🙂")
        else:
            await update.message.reply_text("У вас пока нет задач 🙂")
        return

    try:
        if update.callback_query:
            # Для обработки нажатий на inline-кнопки
            await update.callback_query.edit_message_text(
                text="Ваши задачи:",  # Минимальный текст
                reply_markup=keyboard_markup
            )
        else:
            # Для обработки нажатий на кнопки клавиатуры
            await update.message.reply_text(
                text="Ваши задачи:",  # Минимальный текст
                reply_markup=keyboard_markup
            )
    except Exception as e:
        logger.error(f"Ошибка при отображении списка задач: {e}")
        
        # Отправляем новое сообщение вместо редактирования
        try:
            chat_id = update.effective_chat.id
            await context.bot.send_message(
                chat_id=chat_id,
                text="Ваши задачи:",
                reply_markup=keyboard_markup
            )
        except Exception as e2:
            logger.error(f"Повторная ошибка: {e2}")
            if update.message:
                await update.message.reply_text("Не удалось загрузить список задач. Попробуйте еще раз.")

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
    data = query.data
    user_id = query.from_user.id
    
    if data == "divider":
        # Игнорируем нажатия на разделитель
        await query.answer()
        return
    
    if data == "toggle_all":
        tasks = get_tasks_db(user_id, only_open=False)
        if not tasks:
            await query.answer("Нет задач для изменения")
            return
        
        # Проверяем, есть ли невыполненные задачи
        has_incomplete = any(not task[2] for task in tasks)
        
        # Если есть невыполненные, отмечаем все как выполненные
        # Иначе снимаем отметки со всех
        new_status = 1 if has_incomplete else 0
        
        for task_id, _, _, _ in tasks:  # Добавлен еще один элемент для priority
            toggle_task_status_db(task_id, new_status)
        
        await query.answer("Статус всех задач изменен")
        await list_tasks(update, context)
        return
    
    if data == "priority_mode":
        # Переходим в режим изменения приоритетов
        await show_priority_menu(update, context)
        return
    
    if data.startswith("set_priority_"):
        # Показываем опции приоритета для выбранной задачи
        await show_priority_options(update, context)
        return
    
    if data.startswith("priority_"):
        # Устанавливаем приоритет для задачи
        await set_task_priority(update, context)
        return
    
    if data == "back_to_list":
        # Возвращаемся к списку задач
        await list_tasks(update, context)
        return
    
    if data.startswith("toggle_"):
        task_id = int(data.split("_")[1])
        toggle_task_status_db(task_id)
        await query.answer("Статус задачи изменен")
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
    menu_buttons = ["📋 Мои задачи", "🧹 Удалить выполненные", "❌ Отмена"]
    
    if not text or text.startswith('/'):
        return  # Игнорируем пустые сообщения и команды
    
    # Проверяем, не является ли ввод текстом кнопки меню
    if text in menu_buttons:
        return  # Игнорируем тексты кнопок меню
    
    # Разделяем по ; или по переводу строки
    tasks_list = [task.strip() for task in re.split(r';|\n', text) if task.strip()]
    for task_text in tasks_list:
        add_task_db(user_id, task_text)
    
    logger.info(f"Добавлены задачи через универсальный обработчик: user_id={user_id}, tasks={tasks_list}")
    
    # Сразу показываем список задач (только один раз)
    await list_tasks(update, context)

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
            "Удаление отменено",
            reply_markup=get_main_keyboard()
        )
        return ConversationHandler.END
    
    # Список текстов кнопок, которые не должны обрабатываться как номера задач
    menu_buttons = ["📋 Мои задачи", "🧹 Удалить выполненные", "❌ Отмена"]
    
    if input_text in menu_buttons:
        # Если это кнопка меню, обрабатываем её как нажатие кнопки
        await main_menu_handler(update, context)
        return ConversationHandler.END
    
    input_text = input_text.replace(' ', '')
    tasks = get_tasks_db(user_id, only_open=False)  # Явно указываем параметр
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
            "Нет подходящих задач для удаления",
            reply_markup=get_main_keyboard()
        )
        return ConversationHandler.END

    for task_id in to_delete:
        delete_task_db(task_id, user_id)

    await update.message.reply_text("Выбранные задачи удалены.", reply_markup=get_main_keyboard())
    await list_tasks(update, context)
    return ConversationHandler.END

menu_filter = (
    filters.Regex(r"^📋 Мои задачи$") |
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
        CommandHandler("add", add)
    ],
    states={
        ADDING_TASK: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_task)]
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

    # 6. Запуск бота
    print("Бот запущен! Данные сохраняются в tasks.db.")
    app.run_polling()

if __name__ == "__main__":
    main()