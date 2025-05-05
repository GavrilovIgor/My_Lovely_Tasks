import os
import re
import sqlite3
from datetime import datetime, timedelta, date
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler, CallbackContext
from telegram import BotCommand, BotCommandScopeDefault
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
DB_PATH = "data/tasks.db"
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
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
            priority INTEGER DEFAULT 0,
            reminder_time TIMESTAMP DEFAULT NULL
        )
    """)
    
    # Проверяем, существует ли колонка priority
    c.execute("PRAGMA table_info(tasks)")
    columns = [column[1] for column in c.fetchall()]
    
    # Если колонки priority нет, добавляем ее
    if 'priority' not in columns:
        c.execute("ALTER TABLE tasks ADD COLUMN priority INTEGER DEFAULT 0")
        print("Добавлена колонка priority в таблицу tasks")
    
    # Если колонки reminder_time нет, добавляем ее
    if 'reminder_time' not in columns:
        c.execute("ALTER TABLE tasks ADD COLUMN reminder_time TIMESTAMP DEFAULT NULL")
        print("Добавлена колонка reminder_time в таблицу tasks")
    
    conn.commit()
    conn.close()

def add_task_db(user_id, text, priority=0):
    # Извлекаем время напоминания из текста задачи
    reminder_time, clean_text = extract_reminder_time(text)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    if reminder_time:
        # Если есть напоминание, сохраняем его
        reminder_str = reminder_time.strftime('%Y-%m-%d %H:%M:%S')
        c.execute("""
            INSERT INTO tasks (user_id, text, done, priority, reminder_time) 
            VALUES (?, ?, 0, ?, ?)
        """, (user_id, clean_text, priority, reminder_str))
        task_id = c.lastrowid
        logger.info(f"Добавлена задача с напоминанием: id={task_id}, user_id={user_id}, text='{clean_text}', reminder={reminder_str}")
    else:
        # Если напоминания нет, сохраняем без него
        c.execute("""
            INSERT INTO tasks (user_id, text, done, priority) 
            VALUES (?, ?, 0, ?)
        """, (user_id, text, priority))
        task_id = c.lastrowid
        logger.info(f"Добавлена задача: id={task_id}, user_id={user_id}, text='{text}'")
    
    conn.commit()
    conn.close()
    return task_id

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
        c.execute("""
            SELECT id, text, done, priority, reminder_time 
            FROM tasks 
            WHERE user_id = ? AND done = 0 
            ORDER BY priority DESC, id
        """, (user_id,))
    else:
        c.execute("""
            SELECT id, text, done, priority, reminder_time 
            FROM tasks 
            WHERE user_id = ? 
            ORDER BY priority DESC, id
        """, (user_id,))
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

def extract_reminder_time(text):
    """Извлекает время напоминания из текста задачи"""
    logger.info(f"Обработка текста для напоминания: '{text}'")
    
    # Ищем время в формате @ЧЧ:ММ
    match = re.search(r'@(\d{1,2}):(\d{2})', text)
    if not match:
        logger.info("Напоминание не найдено")
        return None, text
    
    hour = int(match.group(1))
    minute = int(match.group(2))
    logger.info(f"Найдено время: {hour}:{minute}")
    
    # Удаляем напоминание из текста
    clean_text = re.sub(r'@\d{1,2}:\d{2}', '', text).strip()
    
    # Создаем время напоминания
    now = datetime.now()
    reminder_time = datetime(now.year, now.month, now.day, hour, minute)
    
    # Если время уже прошло, устанавливаем на завтра
    if reminder_time < now:
        reminder_time = reminder_time + timedelta(days=1)
    
    logger.info(f"Установлено напоминание на: {reminder_time}")
    return reminder_time, clean_text

def set_reminder(task_id, reminder_time):
    """Устанавливает время напоминания для задачи"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE tasks SET reminder_time = ? WHERE id = ?", 
              (reminder_time.strftime('%Y-%m-%d %H:%M:%S') if reminder_time else None, task_id))
    conn.commit()
    conn.close()
    logger.info(f"Установлено напоминание для задачи id={task_id} на {reminder_time}")

def get_tasks_with_reminders(user_id):
    """Получает список задач с напоминаниями для пользователя"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT id, text, done, priority, reminder_time 
        FROM tasks 
        WHERE user_id = ? AND reminder_time IS NOT NULL
        ORDER BY reminder_time
    """, (user_id,))
    tasks = c.fetchall()
    conn.close()
    return tasks

def check_due_reminders():
    """Проверяет задачи с истекшим временем напоминания"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Выводим все напоминания для отладки
    c.execute("SELECT id, user_id, text, reminder_time FROM tasks WHERE reminder_time IS NOT NULL")
    all_reminders = c.fetchall()
    logger.info(f"Все напоминания в системе: {all_reminders}")
    
    # Проверяем напоминания, время которых наступило
    c.execute("""
        SELECT id, user_id, text, done, reminder_time 
        FROM tasks 
        WHERE reminder_time IS NOT NULL AND reminder_time <= ? AND done = 0
    """, (now,))
    due_tasks = c.fetchall()
    conn.close()
    
    logger.info(f"Проверка напоминаний на {now}: найдено {len(due_tasks)} задач")
    if due_tasks:
        logger.info(f"Задачи с истекшим временем: {due_tasks}")
    return due_tasks

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

    # Статистика с индикатором кликабельности
    total = len(tasks)
    done_count = sum(1 for task in tasks if task[2])
    keyboard.append([
        InlineKeyboardButton(
            text=f"🔄 [ {done_count}/{total} выполнено ]",
            callback_data="toggle_all"
        )
    ])
    
    # Кнопка приоритетов с индикатором кликабельности
    keyboard.append([
        InlineKeyboardButton(
            text=f"🔢 [ Определить приоритет ]",
            callback_data="priority_mode"
        )
    ])
    
    # Кнопка категорий
    keyboard.append([
        InlineKeyboardButton(
            text=f"#️⃣ [ Категории ]",
            callback_data="category_mode"
        )
    ])
    
    # Кнопка напоминаний
    keyboard.append([
        InlineKeyboardButton(
            text=f"🆙 [ Напоминания ]",
            callback_data="reminder_mode"
        )
    ])
    
    # Улучшенный разделитель
    keyboard.append([
        InlineKeyboardButton(text="▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂", callback_data="divider")
    ])

    # Словарь эмодзи для приоритетов
    priority_emoji = {
        3: "🔴", # Высокий
        2: "🟡", # Средний
        1: "🔵"  # Низкий
    }

    for task_id, text, done, priority, reminder_time in tasks:
        # Формируем статус задачи
        status = "✅" if done else "☐"
        
        # Формируем текст задачи с новой структурой
        task_text = f"{status} "
        
        # Добавляем приоритет только если он установлен (не 0)
        if priority > 0:
            priority_icon = priority_emoji.get(priority, "")
            task_text += f"{priority_icon} "
        
        # Добавляем индикатор напоминания, если оно установлено
        if reminder_time:
            task_text += f"🔔 "
        
        # Добавляем текст задачи
        task_text += text
        
        keyboard.append([
            InlineKeyboardButton(
                text=task_text,
                callback_data=f"toggle_{task_id}",
            )
        ])

    return InlineKeyboardMarkup(keyboard) if keyboard else None

async def show_reminders_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    tasks_with_reminders = get_tasks_with_reminders(user_id)
    
    keyboard = []
    keyboard.append([
        InlineKeyboardButton(
            text="Задачи с напоминаниями:",
            callback_data="divider"
        )
    ])
    
    if not tasks_with_reminders:
        keyboard.append([
            InlineKeyboardButton(
                text="У вас нет задач с напоминаниями",
                callback_data="divider"
            )
        ])
        keyboard.append([
            InlineKeyboardButton(
                text="Добавьте @время к задаче для создания напоминания",
                callback_data="divider"
            )
        ])
    else:
        # Словарь эмодзи для приоритетов
        priority_emoji = {
            3: "🔴", # Высокий
            2: "🟡", # Средний
            1: "🔵"  # Низкий
        }
        
        for task_id, text, done, priority, reminder_time in tasks_with_reminders:
            # Преобразуем строку времени в объект datetime
            if reminder_time:
                reminder_dt = datetime.strptime(reminder_time, '%Y-%m-%d %H:%M:%S')
                reminder_str = reminder_dt.strftime('%d.%m %H:%M')
            else:
                reminder_str = "Нет времени"
            
            # Формируем статус задачи
            status = "✅" if done else "☐"
            
            # Добавляем приоритет если он установлен
            priority_icon = ""
            if priority > 0:
                priority_icon = f"{priority_emoji.get(priority, '')} "
            
            task_text = f"{status} {priority_icon}[{reminder_str}] {text}"
            
            keyboard.append([
                InlineKeyboardButton(
                    text=task_text,
                    callback_data=f"reminder_options_{task_id}"
                )
            ])
    
    keyboard.append([
        InlineKeyboardButton(
            text="↩️ Назад к списку задач",
            callback_data="back_to_list"
        )
    ])
    
    await query.edit_message_text(
        text="Управление напоминаниями:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_reminder_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Извлекаем ID задачи из callback_data
    task_id = int(query.data.split('_')[2])
    
    keyboard = [
        [
            InlineKeyboardButton(
                text="❌ Удалить напоминание",
                callback_data=f"delete_reminder_{task_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="⏰ Отложить на 30 минут",
                callback_data=f"snooze_reminder_{task_id}_30"
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
                text="⏰ Отложить на завтра",
                callback_data=f"snooze_reminder_{task_id}_tomorrow"
            )
        ],
        [
            InlineKeyboardButton(
                text="↩️ Назад к напоминаниям",
                callback_data="reminder_mode"
            )
        ]
    ]
    
    await query.edit_message_text(
        text="Выберите действие с напоминанием:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def delete_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Извлекаем ID задачи из callback_data
    task_id = int(query.data.split('_')[2])
    
    # Удаляем напоминание (устанавливаем NULL)
    set_reminder(task_id, None)
    
    # Возвращаемся к списку напоминаний
    await show_reminders_menu(update, context)

async def snooze_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Извлекаем ID задачи и время отсрочки из callback_data
    parts = query.data.split('_')
    task_id = int(parts[2])
    snooze_value = parts[3]
    
    # Получаем текущее время напоминания
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT reminder_time FROM tasks WHERE id = ?", (task_id,))
    result = c.fetchone()
    conn.close()
    
    if result and result[0]:
        current_reminder = datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S')
        
        # Рассчитываем новое время напоминания
        if snooze_value == "tomorrow":
            # Отложить на завтра (то же время)
            new_reminder = current_reminder + timedelta(days=1)
        else:
            # Отложить на указанное количество минут от ТЕКУЩЕГО времени напоминания
            minutes = int(snooze_value)
            new_reminder = current_reminder + timedelta(minutes=minutes)
        
        # Обновляем время напоминания
        set_reminder(task_id, new_reminder)
        logger.info(f"Напоминание отложено с {current_reminder} на {new_reminder}")
    
    # Возвращаемся к списку напоминаний
    await show_reminders_menu(update, context)

async def send_reminder_notification(context):
    """Отправляет уведомления о напоминаниях"""
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

def extract_categories(text):
    """Извлекает хэштеги (категории) из текста задачи"""
    hashtags = re.findall(r'#(\w+)', text)
    return hashtags

async def show_categories_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    tasks = get_tasks_db(user_id, only_open=False)
    
    # Собираем все категории из задач
    categories = {}
    for task_id, text, done, priority, reminder_time in tasks:
        task_categories = extract_categories(text)
        for category in task_categories:
            if category in categories:
                categories[category] += 1
            else:
                categories[category] = 1
    
    keyboard = []
    
    if not categories:
        keyboard.append([
            InlineKeyboardButton(
                text="У вас пока нет категорий",
                callback_data="divider"
            )
        ])
        keyboard.append([
            InlineKeyboardButton(
                text="Напишите в названии новой задачи категорию после знака #",
                callback_data="divider"
            )
        ])
    else:
        keyboard.append([
            InlineKeyboardButton(
                text="Выберите категорию:",
                callback_data="divider"
            )
        ])
        
        # Сортируем категории по количеству задач
        sorted_categories = sorted(categories.items(), key=lambda x: x[1], reverse=True)
        
        for category, count in sorted_categories:
            keyboard.append([
                InlineKeyboardButton(
                    text=f"#{category} ({count})",
                    callback_data=f"filter_category_{category}"
                )
            ])
    
    keyboard.append([
        InlineKeyboardButton(
            text="↩️ Все задачи",
            callback_data="back_to_list"
        )
    ])
    
    await query.edit_message_text(
        text="Категории задач:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
async def show_tasks_by_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Извлекаем категорию из callback_data или из сохраненного контекста
    if hasattr(query, 'data') and query.data.startswith("filter_category_"):
        category = query.data.split('_')[2]
    elif 'current_view' in context.user_data and context.user_data['current_view']['type'] == 'category':
        category = context.user_data['current_view']['category']
    else:
        # Если категория не определена, возвращаемся к списку категорий
        await show_categories_menu(update, context)
        return
    
    user_id = query.from_user.id
    
    # Сохраняем текущую категорию в контексте
    if not hasattr(context, 'user_data'):
        context.user_data = {}
    context.user_data['current_view'] = {
        'type': 'category',
        'category': category
    }
    
    tasks = get_tasks_db(user_id, only_open=False)
    
    keyboard = []
    
    keyboard.append([
        InlineKeyboardButton(
            text=f"Задачи в категории #{category}:",
            callback_data="divider"
        )
    ])
    
    keyboard.append([
        InlineKeyboardButton(text="▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂", callback_data="divider")
    ])
    
    # Словарь эмодзи для приоритетов
    priority_emoji = {
        3: "🔴", # Высокий
        2: "🟡", # Средний
        1: "🔵"  # Низкий
    }
    
    # Фильтруем задачи по категории
    found = False
    for task_id, text, done, priority, reminder_time in tasks:
        if f"#{category}" in text:
            found = True
            # Формируем статус задачи
            status = "✅" if done else "☐"
            
            # Формируем текст задачи
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
    
    if not found:
        keyboard.append([
            InlineKeyboardButton(
                text="В этой категории нет задач",
                callback_data="divider"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton(
            text="↩️ Выбрать другую категорию",
            callback_data="category_mode"
        )
    ])
    
    await query.edit_message_text(
        text=f"Категория #{category}:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_priority_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    tasks = get_tasks_db(user_id, only_open=False)
    
    keyboard = []
    keyboard.append([
        InlineKeyboardButton(
            text="Какой задаче задать приоритет?",
            callback_data="divider"
        )
    ])
    
    # Словарь эмодзи для приоритетов
    priority_emoji = {
        3: "🔴", # Высокий
        2: "🟡", # Средний
        1: "🔵"  # Низкий
    }
    
    for i, (task_id, text, done, priority, reminder_time) in enumerate(tasks, 1):
        # Сокращаем текст, если он слишком длинный
        short_text = text[:30] + "..." if len(text) > 30 else text
        
        # Добавляем текущий приоритет в отображение
        priority_icon = ""
        if priority > 0:
            priority_icon = f"{priority_emoji.get(priority, '')} "
        
        task_text = f"{i}. {priority_icon}{short_text}"
        
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
        
        for task_id, _, _, _, _ in tasks:
            toggle_task_status_db(task_id, new_status)
        
        await query.answer("Статус всех задач изменен")
        await list_tasks(update, context)
        return
    
    if data == "priority_mode":
        # Переходим в режим изменения приоритетов
        await show_priority_menu(update, context)
        return
    
    if data == "category_mode":
        # Переходим в режим просмотра категорий
        await show_categories_menu(update, context)
        return
    
    if data == "reminder_mode":
        # Переходим в режим управления напоминаниями
        await show_reminders_menu(update, context)
        return
    
    if data.startswith("reminder_options_"):
        # Показываем опции для напоминания
        await show_reminder_options(update, context)
        return
    
    if data.startswith("delete_reminder_"):
        # Удаляем напоминание
        await delete_reminder(update, context)
        return
    
    if data.startswith("snooze_reminder_"):
        # Откладываем напоминание
        await snooze_reminder(update, context)
        return
    
    if data.startswith("filter_category_"):
        # Показываем задачи выбранной категории
        await show_tasks_by_category(update, context)
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

    # Проверяем, находимся ли мы в режиме просмотра категории
    if hasattr(context, 'user_data') and 'current_view' in context.user_data and context.user_data['current_view']['type'] == 'category':
        category = context.user_data['current_view']['category']
        # Обновляем список задач в текущей категории
        await show_tasks_by_category(update, context)
    else:
        # Иначе показываем общий список задач
        await list_tasks(update, context)
    return

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

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет сообщение с помощью при команде /help"""
    await update.message.reply_text(
        "Список доступных команд:\n"
        "/start - Начать/перезапустить работу с ботом\n"
        "/help - Показать справку\n"
        "/list - Показать список задач\n\n"
        "Для добавления задачи просто напишите её текст.\n"
        "Для добавления напоминания используйте @время (например: Позвонить @18:00)\n"
        "Для категоризации используйте #категория (например: Купить молоко #покупки)"
    )

async def test_notification(context):
    """Тестовое напоминание"""
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

def main():
    # 1. Создание бота и диспетчера
    app = Application.builder().token(TOKEN).build()
    
    # 2. Инициализация базы данных
    init_db()
    
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
    
    # 4. Добавление обработчиков
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("list", list_tasks))
    
    # Обработчик для кнопок в списке задач
    app.add_handler(CallbackQueryHandler(task_action))
    
    # Обработчик для добавления задач
    app.add_handler(conv_handler)
    
    # Обработчик для текстовых сообщений (добавление задач)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~menu_filter, add_task_from_text))
    
    # Обработчик для кнопок главного меню
    app.add_handler(MessageHandler(menu_filter, main_menu_handler))
    
    # Добавляем планировщик для проверки напоминаний каждую минуту
    job_queue = app.job_queue
    
    # Тестовое напоминание сразу после запуска
    job_queue.run_once(test_notification, 10)
    
    # Проверка напоминаний каждые 30 секунд для более быстрой реакции
    job_queue.run_repeating(send_reminder_notification, interval=30, first=5)
    
    logger.info("Планировщик напоминаний запущен")

    # 5. Запуск бота
    print("Бот запущен! Данные сохраняются в tasks.db.")
    app.run_polling()
if __name__ == "__main__":
    main()