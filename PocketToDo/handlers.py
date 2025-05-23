import sqlite3
import logging
import re
from database import DB_PATH
from typing import List, Tuple, Optional
from datetime import datetime, timedelta, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from database import (
    get_tasks_db, toggle_task_status_db, add_task_db, delete_task_db,
    delete_completed_tasks_for_user, get_tasks_with_reminders, set_reminder,
    update_task_priority, toggle_all_tasks_db
)
from keyboards import get_main_keyboard, get_task_list_markup, get_cancel_keyboard
from utils import extract_categories

logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
ADDING_TASK = 1
DELETING_TASKS = 2

# Единый список кнопок меню
MENU_BUTTONS = ["📋 Мои задачи", "🧹 Удалить выполненные", "❌ Отмена"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик команды /start
    
    Args:
        update: Объект обновления Telegram
        context: Контекст бота
    """
    await update.message.reply_text(
        "😺 Привет, организованный человек! Я – твой карманный помощник для задач!\n\n"
        "📝 Я создан, чтобы твоё \"Избранное\" не превращалось в свалку списков дел, а жизнь стала проще! \n\n"
        "✨ Что я умею:\n"
        "- Добавлять задачи (просто напиши мне что нужно сделать!)\n"
        "- Отмечать выполненные (приятное чувство, когда вычёркиваешь дела ✅)\n"
        "- Удалять ненужное (чистота – залог продуктивности! 😊)\n\n"
        "🚀 Начнём вместе делать твои дела? Просто напиши мне задачу!",
        reply_markup=get_main_keyboard()
    )
 # Показываем краткий гайд только если не показывали ранее
    if not context.user_data.get('hint_start_shown'):
        await update.message.reply_text(
            "ℹ️ Добро пожаловать ✋\n\n"
            "Вот как легко мной пользоваться:\n\n"
            "✨ Просто напиши свою задачу, например:\n"
            "Купить колбаски \n\n"
            "✨ Хочешь добавить сразу несколько задач? Пиши каждую с новой строки:\n"
            "Погладить кота\nКупить хлеб\nПозвонить маме\n\n"
            "✨ Важно не забыть? Поставь напоминание, указав время в задаче:\n"
            "Позвонить братишке 18:00\nЗаписаться к врачу 'дата' 10:00\n\n"
            "✨ Хочешь разделить задачи по темам? Используй #теги:\n"
            "Сделать отчёт #работа\nЗабрать племянника из школы #семья\n\n"
            "✨ Нужно сфокусироваться на важном? Добавь приоритет с помощью !:\n"
            "Записаться на тех.осмотр !важно\nКупить билеты на концерт !низкий\n\n"
            "✨ Всё вместе может выглядеть так:\n"
            "Поставить встречу с командой #работа !срочно 13:35\n\n"
            "❓ Если вдруг что-то забыл - просто набери /help или выбери /help в меню!\n\n"
            "Вперед 🚀",
            reply_markup=get_main_keyboard()
        )
        context.user_data['hint_start_shown'] = True
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Отправляет сообщение с помощью при команде /help
    
    Args:
        update: Объект обновления Telegram
        context: Контекст бота
    """
    await update.message.reply_text(
        "ℹ️ Вот как легко мной пользоваться:\n\n"
            "✨ Просто напиши свою задачу, например:\n"
            "Купить колбаски \n\n"
            "✨ Хочешь добавить сразу несколько задач? Пиши каждую с новой строки:\n"
            "Погладить кота\nКупить хлеб\nПозвонить маме\n\n"
            "✨ Важно не забыть? Поставь напоминание указав время в задаче:\n"
            "Позвонить братишке 18:00\nЗаписаться к врачу 'дата' 10:00\n\n"
            "✨ Хочешь разделить задачи по темам? Используй #теги:\n"
            "Сделать отчёт #работа\nЗабрать племянника из школы #семья\n\n"
            "✨ Нужно сфокусироваться на важном? Добавь приоритет с помощью !:\n"
            "Записаться на тех.осмотр !важно\nКупить билеты на концерт !низкий\n\n"
            "✨ Всё вместе может выглядеть так:\n"
            "Поставить встречу с командой #работа !срочно 13:35\n\n"
            "❓ Если вдруг что-то забыл - просто набери /help или выбери /help в меню!\n\n"
            "Удачи! Ты справишься 😎"
    )

async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Показывает список задач пользователя
    
    Args:
        update: Объект обновления Telegram
        context: Контекст бота
    """
    user_id = update.effective_user.id
    tasks = get_tasks_db(user_id, only_open=False)
    
    # Устанавливаем флаги в контексте
    if hasattr(context, 'user_data'):
        context.user_data['active_task_list'] = True
        context.user_data['active_category_view'] = False
    
    # Создаем клавиатуру
    keyboard_markup = get_task_list_markup(user_id)
    
    # Если у пользователя нет задач
    if not tasks:
        message = "У вас пока нет задач 🙂"
        if update.callback_query:
            await update.callback_query.answer(message)
        else:
            await update.message.reply_text(message)
        return

    # Отправляем или обновляем сообщение со списком задач
    try:
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text="Ваши задачи:",
                reply_markup=keyboard_markup
            )
        else:
            await update.message.reply_text(
                text="Ваши задачи:",
                reply_markup=keyboard_markup
            )
    except Exception as e:
        logger.error(f"Ошибка при отображении списка задач: {e}")
        
        # Если не удалось отредактировать сообщение, отправляем новое
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

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Начинает процесс добавления задачи
    
    Args:
        update: Объект обновления Telegram
        context: Контекст бота
        
    Returns:
        int: Следующее состояние разговора
    """
    await update.message.reply_text(
        "Вводите задачи с новой строки или через точку с запятой (например: Задача 1\nЗадача 2\n или\nЗадача 1; Задача 2)",
        reply_markup=get_cancel_keyboard()
    )
    return ADDING_TASK

async def save_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Сохраняет новую задачу
    
    Args:
        update: Объект обновления Telegram
        context: Контекст бота
        
    Returns:
        int: Следующее состояние разговора
    """
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
    MENU_BUTTONS = ["📋 Мои задачи", "🧹 Удалить выполненные", "❌ Отмена"]
    
    if not input_text:
        await update.message.reply_text("Пустой ввод. Попробуйте снова.")
        return ConversationHandler.END
    
    # Проверяем, не является ли ввод текстом кнопки меню
    if input_text in MENU_BUTTONS:
        # Если это кнопка меню, обрабатываем её как нажатие кнопки
        await main_menu_handler(update, context)
        return ConversationHandler.END
    
    tasks_list = [task.strip() for task in re.split(r';|\n', input_text) if task.strip()]
    
    for task_text in tasks_list:
        add_task_db(user_id, task_text)
    
    # Проверяем, находимся ли мы в режиме просмотра категории
    if hasattr(context, 'user_data') and context.user_data.get('active_category_view', False):
        # Обновляем список задач в текущей категории
        await show_tasks_by_category(update, context)
    else:
        # В остальных случаях показываем общий список задач
        await list_tasks(update, context)
    
    return ConversationHandler.END

async def add_task_from_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Добавляет задачу из текстового сообщения
    
    Args:
        update: Объект обновления Telegram
        context: Контекст бота
    """
    user_id = update.message.from_user.id
    text = update.message.text.strip()
    
    # Список текстов кнопок, которые не должны добавляться как задачи
    MENU_BUTTONS = ["📋 Мои задачи", "🧹 Удалить выполненные", "❌ Отмена"]
    
    if not text or text.startswith('/') or text in MENU_BUTTONS: return
    
    # Проверяем, не является ли ввод текстом кнопки меню
    if text in MENU_BUTTONS:
        return  # Игнорируем тексты кнопок меню
    
    # Разделяем по ; или по переводу строки
    tasks_list = [task.strip() for task in re.split(r';|\n', text) if task.strip()]
    for task_text in tasks_list:
        add_task_db(user_id, task_text)
    
    logger.info(f"Добавлены задачи через универсальный обработчик: user_id={user_id}, tasks={tasks_list}")
    
    # Проверяем, находимся ли мы в режиме просмотра категории
    if hasattr(context, 'user_data') and context.user_data.get('active_category_view', False):
        # Обновляем список задач в текущей категории
        await show_tasks_by_category(update, context)
    else:
        # В остальных случаях показываем общий список задач
        await list_tasks(update, context)

async def main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[int]:
    """
    Обработчик кнопок главного меню
    
    Args:
        update: Объект обновления Telegram
        context: Контекст бота
        
    Returns:
        Optional[int]: Следующее состояние разговора или None
    """
    try:
        text = update.message.text
        if text == "➕ Добавить задачу":
            return await add(update, context)
        elif text == "📋 Мои задачи":
            # Добавляем логирование для отладки
            logger.info(f"Нажата кнопка 'Мои задачи' пользователем {update.effective_user.id}")
            await list_tasks(update, context)
            return ConversationHandler.END
        elif text == "🗑 Удалить задачу":
            return await ask_delete_tasks(update, context)
        elif text == "🧹 Удалить выполненные":
            user_id = update.message.from_user.id
            delete_completed_tasks_for_user(user_id)
            await update.message.reply_text("Выполненные задачи удалены.", reply_markup=get_main_keyboard())
            
            # Проверяем, находимся ли мы в режиме просмотра категории
            if hasattr(context, 'user_data') and context.user_data.get('active_category_view', False):
                # Обновляем список задач в текущей категории
                await show_tasks_by_category(update, context)
            else:
                # В остальных случаях показываем общий список задач
                await list_tasks(update, context)
            
            return ConversationHandler.END
    except Exception as e:
        logger.error(f"Ошибка в обработчике главного меню: {e}")
        return ConversationHandler.END

async def ask_delete_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Запрашивает у пользователя номера задач для удаления
    
    Args:
        update: Объект обновления Telegram
        context: Контекст бота
        
    Returns:
        int: Следующее состояние разговора
    """
    await update.message.reply_text(
        "Введите номера задач для удаления через запятую или диапазон (например: 1,3,5-7):",
        reply_markup=get_cancel_keyboard()
    )
    return DELETING_TASKS

async def delete_tasks_by_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Удаляет задачи по номерам, указанным пользователем
    
    Args:
        update: Объект обновления Telegram
        context: Контекст бота
        
    Returns:
        int: Следующее состояние разговора
    """
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
    MENU_BUTTONS = ["📋 Мои задачи", "🧹 Удалить выполненные", "❌ Отмена"]
    
    if input_text in MENU_BUTTONS:
        # Если это кнопка меню, обрабатываем её как нажатие кнопки
        await main_menu_handler(update, context)
        return ConversationHandler.END
    
    input_text = input_text.replace(' ', '')
    tasks = get_tasks_db(user_id, only_open=False)
    to_delete = set()

    # Разбиваем по запятой
    for part in input_text.split(','):
        if '-' in part:
            start_end = part.split('-')
            if len(start_end) == 2 and start_end[0].isdigit() and start_end[1].isdigit():
                start, end = map(int, start_end)
                for n in range(start, end + 1):
                    if 1 <= n <= len(tasks):
                        to_delete.add(tasks[n-1][0])

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

async def task_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает действия с задачами через inline-кнопки
    
    Args:
        update: Объект обновления Telegram
        context: Контекст бота
    """
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
        # Сбрасываем флаг активного просмотра категории
        if hasattr(context, 'user_data'):
            context.user_data['active_category_view'] = False
        # Возвращаемся к списку задач
        await list_tasks(update, context)
        return

    if data.startswith("toggle_"):
        task_id = int(data.split("_")[1])
        toggle_task_status_db(task_id)
        await query.answer("Статус задачи изменен")
        
        # Проверяем, находимся ли мы в режиме просмотра категории
        if hasattr(context, 'user_data') and context.user_data.get('active_category_view', False):
            # Обновляем список задач в текущей категории
            await show_tasks_by_category(update, context)
            return
        else:
            # В остальных случаях показываем общий список задач
            await list_tasks(update, context)
            return

async def show_priority_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Показывает меню изменения приоритетов задач
    
    Args:
        update: Объект обновления Telegram
        context: Контекст бота
    """
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

async def show_priority_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Показывает варианты приоритетов для задачи
    
    Args:
        update: Объект обновления Telegram
        context: Контекст бота
    """
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

async def set_task_priority(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Устанавливает приоритет для задачи
    
    Args:
        update: Объект обновления Telegram
        context: Контекст бота
    """
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

async def show_categories_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Показывает меню категорий задач
    """
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
    
    # Заголовок для меню категорий
    if not categories:
        keyboard.append([
            InlineKeyboardButton(
                text="У вас пока нет категорий",
                callback_data="divider"
            )
        ])
        keyboard.append([
            InlineKeyboardButton(
                text="Добавьте #категорию к задаче",
                callback_data="divider"
            )
        ])
    else:
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
            text="↩️ Назад к задачам",
            callback_data="back_to_list"
        )
    ])
    
    # Редактируем текущее сообщение вместо отправки нового
    await query.edit_message_text(
        text="Категории задач:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_tasks_by_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Показывает задачи по выбранной категории
    
    Args:
        update: Объект обновления Telegram
        context: Контекст бота
    """
    query = update.callback_query
    user_id = update.effective_user.id
    
    # Извлекаем категорию из callback_data или из сохраненного контекста
    if query and hasattr(query, 'data') and query.data.startswith("filter_category_"):
        category = query.data.split('_')[2]
        await query.answer()
    elif hasattr(context, 'user_data') and 'current_view' in context.user_data and context.user_data['current_view']['type'] == 'category':
        category = context.user_data['current_view']['category']
    else:
        # Если категория не определена, возвращаемся к списку категорий
        if query:
            await query.answer()
            await show_categories_menu(update, context)
        return
    
    # Сохраняем текущую категорию в контексте
    if not hasattr(context, 'user_data'):
        context.user_data = {}
    
    context.user_data['current_view'] = {
        'type': 'category',
        'category': category
    }
    # Устанавливаем флаг активного просмотра категории
    context.user_data['active_category_view'] = True
    # Сбрасываем флаг активного списка задач
    context.user_data['active_task_list'] = False

    tasks = get_tasks_db(user_id, only_open=False)
    
    keyboard = []
    keyboard.append([
        InlineKeyboardButton(
            text=f"Задачи в категории #{category}:",
            callback_data="divider"
        )
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
        task_categories = extract_categories(text)
        if category in task_categories:
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
    
    message_text = f"Категория #{category}:"
    
    # Если это callback_query, редактируем существующее сообщение
    if query:
        try:
            await query.edit_message_text(
                text=message_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            # Если сообщение не изменилось, телеграм выдаст ошибку
            # В этом случае просто игнорируем ее
            logger.info(f"Не удалось обновить сообщение: {e}")
            # Если не удалось отредактировать, отправляем новое
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=message_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    else:
        # Если это не callback_query (например, команда), отправляем новое сообщение
        await update.effective_message.reply_text(
            text=message_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def show_reminders_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Показывает меню управления напоминаниями
    
    Args:
        update: Объект обновления Telegram
        context: Контекст бота
    """
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
                text="Добавьте время к задаче для создания напоминания",
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

async def show_reminder_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Показывает опции для напоминания
    
    Args:
        update: Объект обновления Telegram
        context: Контекст бота
    """
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

async def delete_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Удаляет напоминание для задачи
    
    Args:
        update: Объект обновления Telegram
        context: Контекст бота
    """
    query = update.callback_query
    await query.answer()
    
    # Извлекаем ID задачи из callback_data
    task_id = int(query.data.split('_')[2])
    
    # Удаляем напоминание (устанавливаем NULL)
    set_reminder(task_id, None)
    
    # Возвращаемся к списку напоминаний
    await show_reminders_menu(update, context)

async def send_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Отправляет напоминание о задаче
    
    Args:
        context: Контекст бота с данными задачи
    """
    job = context.job
    task_id, user_id, task_text = job.data
    
    # Создаем клавиатуру для напоминания с тремя вариантами
    keyboard = [
        [
            InlineKeyboardButton(
                text="✅ Выполнено / Отмена задачи",
                callback_data=f"toggle_{task_id}"
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
                text="📆 Отложить на завтра",
                callback_data=f"snooze_reminder_{task_id}_tomorrow"
            )
        ]
    ]
    
    await context.bot.send_message(
        chat_id=user_id,
        text=f"🔔 Напоминание: {task_text}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def snooze_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    parts = query.data.split('_')
    task_id = int(parts[2])
    snooze_value = parts[3]

    # Всегда работаем в московской зоне (UTC+3)
    now = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=3)))

    # Получаем исходное время напоминания из БД
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT reminder_time FROM tasks WHERE id = ?", (task_id,))
    result = c.fetchone()
    conn.close()

    reminder_time = None
    if result and result[0]:
        try:
            reminder_time = datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone(timedelta(hours=3)))
        except Exception:
            reminder_time = now  # fallback

    if snooze_value == "tomorrow":
        # Переносим на завтра в то же время, что было у исходного напоминания
        if reminder_time:
            new_reminder = reminder_time + timedelta(days=1)
        else:
            new_reminder = now + timedelta(days=1)
        new_reminder = new_reminder.replace(second=0)
    else:
        try:
            minutes = int(snooze_value)
            new_reminder = now + timedelta(minutes=minutes)
            new_reminder = new_reminder.replace(second=0)
        except Exception:
            new_reminder = now + timedelta(hours=1)
            new_reminder = new_reminder.replace(second=0)

    set_reminder(task_id, new_reminder)
    logger.info(f"Напоминание отложено на {new_reminder}")

    await query.edit_message_text(
        text=f"Напоминание отложено на {new_reminder.strftime('%d.%m.%Y %H:%M')}",
        reply_markup=None
    )

    # Запускаем новое напоминание
    task_text = get_task_text_by_id(task_id)
    if task_text:
        job_name = f"reminder_{task_id}"
        current_jobs = context.job_queue.get_jobs_by_name(job_name)
        for job in current_jobs:
            job.schedule_removal()

        context.job_queue.run_once(
            send_reminder,
            when=(new_reminder - now).total_seconds(),
            data=(task_id, query.from_user.id, task_text),
            name=job_name
        )

def get_task_text_by_id(task_id: int) -> Optional[str]:
    """
    Получает текст задачи по её ID
    
    Args:
        task_id: ID задачи
        
    Returns:
        Текст задачи или None, если задача не найдена
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT text FROM tasks WHERE id = ?", (task_id,))
    result = c.fetchone()
    conn.close()
    
    return result[0] if result else None

