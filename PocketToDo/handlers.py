import sqlite3
import logging
import re
import os
import requests
import uuid
import base64
from database import DB_PATH
from typing import List, Tuple, Optional
from datetime import datetime, timedelta, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import ContextTypes, ConversationHandler, PreCheckoutQueryHandler


from database import (
    get_tasks_db, toggle_task_status_db, add_task_db, delete_task_db,
    delete_completed_tasks_for_user, get_tasks_with_reminders, set_reminder,
    update_task_priority, toggle_task_db, get_user_donations_db, get_total_donations_db, add_donation_db)
from keyboards import get_main_keyboard, get_task_list_markup, get_cancel_keyboard, priority_emoji
from utils import extract_categories

logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
ADDING_TASK = 1
DELETING_TASKS = 2
SETTING_CUSTOM_REMINDER = 3

# Единый список кнопок меню  
MENU_BUTTONS = ["📋 Мои задачи", "🧹 Удалить выполненные", "🫶 Поддержи проект", "❌ Отмена"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик команды /start
    
    Args:
        update: Объект обновления Telegram
        context: Контекст бота
    """
    # Сбрасываем состояние остановки
    if not hasattr(context, 'user_data'):
        context.user_data = {}
    context.user_data['bot_stopped'] = False
    
    await update.message.reply_text(
        "😺 Привет, организованный человек! Я – твой карманный помощник для задач!\n\n"
        "📝 Я создан, чтобы твоё \"Избранное\" не превращалось в свалку списков дел, а жизнь стала проще! \n\n"
        "✨ Что я умею:\n"
        "- Добавлять задачи (просто напиши мне что нужно сделать!)\n"
        "- Отмечать выполненные (приятное чувство, когда вычёркиваешь дела ✅)\n"
        "- Удалять ненужное (чистота – залог продуктивности! 😊)\n\n"
        "🚀 Начнём вместе делать твои дела? Просто напиши мне задачу!\n\n"
        "💡 Используйте /stop чтобы остановить бота и убрать клавиатуру",
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
            "✨ Важно не забыть? Поставь напоминание, указав время в задаче:\n"
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
async def stop_bot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Остановка бота для пользователя"""
    user_id = update.effective_user.id
    
    # Сохраняем состояние остановки в context.user_data
    if not hasattr(context, 'user_data'):
        context.user_data = {}
    context.user_data['bot_stopped'] = True
    
    # Убираем клавиатуру
    from telegram import ReplyKeyboardRemove
    await update.message.reply_text(
        "🛑 Бот остановлен!\n\n"
        "Чтобы снова запустить бота, используйте команду /start",
        reply_markup=ReplyKeyboardRemove()
    )
    
    logger.info(f"Bot stopped for user {user_id}")

async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type in ['group', 'supergroup']:
        entity_id = update.effective_chat.id
    else:
        entity_id = update.effective_user.id
    tasks = get_tasks_db(entity_id, only_open=False)

    # Устанавливаем флаги в контексте
    if hasattr(context, 'user_data'):
        context.user_data['active_task_list'] = True
        context.user_data['active_category_view'] = False
    
    # Создаем клавиатуру
    keyboard_markup = get_task_list_markup(entity_id)

    # Отправляем или обновляем сообщение со списком задач
    try:
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text="📋 Мои задачи",
                reply_markup=keyboard_markup
            )
        else:
            await update.message.reply_text(
                text="📋 Мои задачи",
                reply_markup=keyboard_markup
            )
    except Exception as e:
        # Игнорируем ошибку "Message is not modified"
        if "Message is not modified" in str(e):
            logger.info("Сообщение не изменилось, пропускаем обновление")
            return
        
        logger.error(f"Ошибка при отображении списка задач: {e}")
        # Если не удалось отредактировать сообщение, отправляем новое
        try:
            chat_id = update.effective_chat.id
            await context.bot.send_message(
                chat_id=chat_id,
                text="Мои задачи:",
                reply_markup=keyboard_markup
            )
        except Exception as e2:
            logger.error(f"Повторная ошибка: {e2}")

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
    # Определяем owner_id для группы или лички
    if update.effective_chat.type in ['group', 'supergroup']:
        owner_id = update.effective_chat.id
    else:
        owner_id = update.effective_user.id

    input_text = update.message.text.strip()

    # Проверяем, нажал ли пользователь кнопку отмены
    if input_text == "❌ Отмена":
        await update.message.reply_text(
            "Добавление отменено.",
            reply_markup=get_main_keyboard()
        )
        return ConversationHandler.END

    # Список текстов кнопок, которые не должны добавляться как задачи
    MENU_BUTTONS = ["📋 Мои задачи", "🧹 Удалить выполненные", "🫶 Поддержи проект", "❌ Отмена"]

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
        add_task_db(owner_id, task_text)

    # Проверяем, находимся ли мы в режиме просмотра категории
    if hasattr(context, 'user_data') and context.user_data.get('active_category_view', False):
        # Обновляем список задач в текущей категории
        await show_tasks_by_category(update, context)
    else:
        # В остальных случаях показываем общий список задач
        await list_tasks(update, context)

    return ConversationHandler.END

async def add_task_from_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(f"add_task_from_text called with text: '{update.message.text}'")
    
    # Проверяем, остановлен ли бот для пользователя
    if hasattr(context, 'user_data') and context.user_data.get('bot_stopped', False):
        logger.info("Bot is stopped for user")
        return
    
    # Простая проверка: если пользователь в процессе установки напоминания
    if (hasattr(context, 'user_data') and 
        context.user_data.get('reminder_task_id')):
        logger.info("User is setting reminder")
        return
    
    # Проверяем, ожидается ли ввод суммы пожертвования
    if hasattr(context, 'user_data') and context.user_data.get('waiting_custom_amount'):
        await handle_custom_donation_amount(update, context)
        return
    
    MENU_BUTTONS = ["📋 Мои задачи", "🧹 Удалить выполненные", "🫶 Поддержи проект", "❌ Отмена"]
    text = update.message.text.strip()
    if not text or text.startswith("/") or text in MENU_BUTTONS:
        return

    # Получаем username бота
    bot_username = (await context.bot.get_me()).username
    mention = f"@{bot_username}"

    # Определяем owner_id и task_text
    if update.effective_chat.type in ['group', 'supergroup']:
        if not text.startswith(mention):
            return  # В группе реагируем только на сообщения с упоминанием
        task_text = text[len(mention):].strip()
        if not task_text:
            return
        owner_id = update.effective_chat.id
    else:
        task_text = text
        owner_id = update.effective_user.id

    tasks_list = [task.strip() for task in re.split(r";|\n", task_text) if task.strip()]
    for task_text in tasks_list:
        add_task_db(owner_id, task_text)

    logger.info(f"owner_id={owner_id}, tasks={tasks_list}")

    if hasattr(context, "user_data") and context.user_data.get("active_category_view", False):
        await show_tasks_by_category(update, context)
    else:
        await list_tasks(update, context)

async def main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[int]:
    # Проверяем, остановлен ли бот для пользователя
    if hasattr(context, 'user_data') and context.user_data.get('bot_stopped', False):
        return ConversationHandler.END

    try:
        text = update.message.text
        if text == "➕ Добавить задачу":
            return await add(update, context)
        elif text == "📋 Мои задачи":

            logger.info(f"Нажата кнопка 'Мои задачи' пользователем {update.effective_user.id}")
            await list_tasks(update, context)
            return ConversationHandler.END
        elif text == "🗑 Удалить задачу":
            return await ask_delete_tasks(update, context)
        elif text == "🧹 Удалить выполненные":
            if update.effective_chat.type in ['group', 'supergroup']:
                owner_id = update.effective_chat.id
            else:
                owner_id = update.effective_user.id
            delete_completed_tasks_for_user(owner_id)
            if hasattr(context, 'user_data') and context.user_data.get('active_category_view', False):
                await show_tasks_by_category(update, context)
            else:
                await list_tasks(update, context)
            return ConversationHandler.END
        elif text == "🫶 Поддержи проект":
            await support_developer(update, context)
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
    # Определяем owner_id для группы или лички
    if update.effective_chat.type in ['group', 'supergroup']:
        owner_id = update.effective_chat.id
    else:
        owner_id = update.effective_user.id

    input_text = update.message.text.strip()

    # Проверяем, нажал ли пользователь кнопку отмены
    if input_text == "❌ Отмена":
        await update.message.reply_text(
            "Удаление отменено",
            reply_markup=get_main_keyboard()
        )
        return ConversationHandler.END

    # Список текстов кнопок, которые не должны обрабатываться как номера задач
    MENU_BUTTONS = ["📋 Мои задачи", "🧹 Удалить выполненные", "🫶 Поддержи проект", "❌ Отмена"]

    if input_text in MENU_BUTTONS:
        # Если это кнопка меню, обрабатываем её как нажатие кнопки
        await main_menu_handler(update, context)
        return ConversationHandler.END

    input_text = input_text.replace(' ', '')
    tasks = get_tasks_db(owner_id, only_open=False)
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
        elif part.isdigit():
            n = int(part)
            if 1 <= n <= len(tasks):
                to_delete.add(tasks[n-1][0])

    if not to_delete:
        await update.message.reply_text(
            "Нет подходящих задач для удаления",
            reply_markup=get_main_keyboard()
        )
        return ConversationHandler.END

    deleted_count = 0
    for task_id in to_delete:
        try:
            delete_task_db(task_id, owner_id)
            deleted_count += 1
        except Exception as e:
            logger.error(f"Ошибка удаления задачи {task_id}: {e}")

    if deleted_count > 0:
        await update.message.reply_text(f"Удалено {deleted_count} задач.", reply_markup=get_main_keyboard())
    else:
        await update.message.reply_text("Не удалось удалить задачи.", reply_markup=get_main_keyboard())

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

    # Определяем owner_id для группы или лички
    if update.effective_chat.type in ['group', 'supergroup']:
        owner_id = update.effective_chat.id
    else:
        owner_id = query.from_user.id

    if data == "divider":
        await query.answer()
        return

    if data == "toggle_all":
        tasks = get_tasks_db(owner_id, only_open=False)
        if not tasks:
            await query.answer("Нет задач для изменения")
            return

        has_incomplete = any(not task[2] for task in tasks)
        new_status = 1 if has_incomplete else 0

        for task_id, _, _, _, _ in tasks:
            toggle_task_status_db(task_id, new_status)

        await query.answer("Статус всех задач изменён")
        await list_tasks(update, context)
        return

    if data == "priority_mode":
        await show_priority_menu(update, context)
        return

    if data == "category_mode":
        await show_categories_menu(update, context)
        return

    if data == "reminder_mode":
        await show_reminders_menu(update, context)
        return

    if data.startswith("reminder_options_"):
        await show_reminder_options(update, context)
        return

    if data.startswith("delete_reminder_"):
        await delete_reminder(update, context)
        return

    if data.startswith("snooze_reminder_"):
        await snooze_reminder(update, context)
        return

    if data.startswith("filter_category_"):
        await show_tasks_by_category(update, context)
        return

    if data.startswith("set_priority_"):
        await show_priority_options(update, context)
        return

    if data.startswith("priority_"):
        await set_task_priority(update, context)
        return

    if data.startswith('category_priority_mode_'):
        await show_category_priority(update, context)
        return

    if data.startswith('category_reminder_mode_'):
        await show_category_reminder(update, context)
        return

    if data.startswith('toggle_all_category_'):
        await toggle_all_category_tasks(update, context)
        return

    if data == "back_to_list":
        if hasattr(context, "user_data") and context.user_data.get("active_category_view", False):
            # Если мы в режиме просмотра категории, возвращаемся к списку категорий
            context.user_data["active_category_view"] = False
            await show_categories_menu(update, context)
        else:
            # Иначе возвращаемся к общему списку задач
            await list_tasks(update, context)
        return

    if data.startswith("toggle"):
        task_id = int(data.split("_")[1])
        success = toggle_task_db(task_id, owner_id)
        if success:
            await query.answer("✅")
        else:
            await query.answer("❌")
            return
        
        # Сначала проверяем, находимся ли мы в режиме просмотра категории
        if hasattr(context, 'user_data') and context.user_data.get("active_category_view", False):
            # Если в категории - обновляем представление категории
            await show_tasks_by_category(update, context)
        else:
            # Если в общем списке - обновляем только клавиатуру без перезагрузки сообщения
            try:
                keyboard_markup = get_task_list_markup(owner_id)
                await query.edit_message_reply_markup(reply_markup=keyboard_markup)
            except Exception as e:
                if "Message is not modified" not in str(e):
                    logger.error(f"Error updating keyboard: {e}")
                # Если не удалось обновить клавиатуру, обновляем весь список
                await list_tasks(update, context)
        return


async def show_priority_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    if not hasattr(context, 'user_data'):
        context.user_data = {}
    
    if update.effective_chat.type in ['group', 'supergroup']:
        owner_id = update.effective_chat.id
    else:
        owner_id = query.from_user.id
    
    tasks = get_tasks_db(owner_id, only_open=False)
    
    keyboard = []
    
    priority_emoji = {3: "🔴", 2: "🟡", 1: "🔵"}
    
    for i, (task_id, text, done, priority, reminder_time) in enumerate(tasks, 1):
        # Формируем текст задачи с приоритетом
        status = "✅" if done else "☐"
        
        # Правильно инициализируем task_text
        task_text = status
        
        if priority > 0:
            priority_icon = priority_emoji.get(priority, "")
            task_text = f"{status}{priority_icon}"
        
        # Добавляем текст задачи
        task_text = f"{task_text} {text}"
            
        keyboard.append([InlineKeyboardButton(
            text=task_text, 
            callback_data=f"set_priority_{task_id}"
        )])
    
    keyboard.append([InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_list")])
    
    await query.edit_message_text(
        text="🔢 *Режим изменения приоритетов*\n\nВыберите задачу для изменения приоритета:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def show_priority_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    # Извлекаем task_id из callback_data
    task_id = int(query.data.split("_")[2])  # set_priority_123 -> 123
    
    # Определяем куда возвращаться
    back_callback = "priority_mode"
    current_category = ""
    if hasattr(context, 'user_data') and context.user_data.get('active_category_view', False):
        current_category = context.user_data.get('current_category', "")
        back_callback = f"category_priority_mode_{current_category}"
    
    keyboard = [
        [InlineKeyboardButton(text="🔴 Высокий", callback_data=f"priority_{task_id}_3")],
        [InlineKeyboardButton(text="🟡 Средний", callback_data=f"priority_{task_id}_2")],
        [InlineKeyboardButton(text="🔵 Низкий", callback_data=f"priority_{task_id}_1")],
        [InlineKeyboardButton(text="Без приоритета", callback_data=f"priority_{task_id}_0")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data=back_callback)]
    ]
    
    await query.edit_message_text(
        text="🔢 Выберите приоритет для задачи:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    await query.edit_message_text(
        text="Выберите приоритет для задачи:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def set_task_priority(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    task_id = int(parts[1])
    priority = int(parts[2])
    update_task_priority(task_id, priority)
    
    if hasattr(context, 'user_data') and context.user_data.get('active_category_view', False):
        # Получаем текущую категорию и возвращаемся к меню приоритетов категории
        current_category = context.user_data.get('current_category', '')
        # Создаем новый Update с правильным callback_data
        from types import SimpleNamespace
        new_query = SimpleNamespace()
        new_query.data = f'category_priority_mode_{current_category}'
        new_query.answer = query.answer
        new_query.edit_message_text = query.edit_message_text
        new_query.from_user = query.from_user
        
        # Создаем новый Update
        new_update = SimpleNamespace()
        new_update.callback_query = new_query
        new_update.effective_chat = update.effective_chat
        
        await show_category_priority(new_update, context)
    else:
        await show_priority_menu(update, context)

async def show_categories_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Показывает меню категорий задач
    """
    query = update.callback_query
    await query.answer()
    
    # Сбрасываем контекст категории при входе в общий режим категорий
    if not hasattr(context, 'user_data'):
        context.user_data = {}
    context.user_data['active_category_view'] = False
    context.user_data['current_category'] = ''

    if update.effective_chat.type in ['group', 'supergroup']:
        owner_id = update.effective_chat.id
    else:
        owner_id = query.from_user.id
    tasks = get_tasks_db(owner_id, only_open=False)

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
                text="Напишите задачу и #категория",
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
            text="↩️ Назад",
            callback_data="back_to_list"
        )
    ])
    
    # Редактируем текущее сообщение вместо отправки нового
    await query.edit_message_text(
        text="Категории задач:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_tasks_by_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать задачи определенной категории"""
    query = update.callback_query
    if update.effective_chat.type in ['group', 'supergroup']:
        owner_id = update.effective_chat.id
    else:
        owner_id = update.effective_user.id if not query else query.from_user.id
    
    # Получаем категорию из callback_data или из context
    if query and hasattr(query, 'data') and query.data.startswith('filter_category_'):
        category = query.data.split('_', 2)[2]
        await query.answer()
    elif hasattr(context, 'user_data') and 'current_view' in context.user_data and context.user_data['current_view']['type'] == 'category':
        category = context.user_data['current_view']['category']
    else:
        return
    
    # Получаем все задачи пользователя
    tasks = get_tasks_db(owner_id, only_open=False)
    
    # Фильтруем задачи по категории
    from utils import extract_categories
    filtered_tasks = []
    for task in tasks:
        task_id, text, done, priority, reminder_time = task
        task_categories = extract_categories(text)
        if category in task_categories:
            filtered_tasks.append(task)
    
    # Подсчитываем выполненные задачи
    done_count = sum(1 for task in filtered_tasks if task[2])  # task[2] это done
    total_count = len(filtered_tasks)
    
    # Создаем клавиатуру
    keyboard = []
    
    # Добавляем кнопку статуса выполнения (отдельная строка)
    keyboard.append([
        InlineKeyboardButton(text=f"🔄 [ {done_count}/{total_count} ] [ Отметить все ]", callback_data=f"toggle_all_category_{category}")
    ])
    
    # Добавляем кнопку приоритетов (отдельная строка)
    keyboard.append([
        InlineKeyboardButton(text="🔢 [ Приоритет ]", callback_data=f"category_priority_mode_{category}")
    ])
    
    # Добавляем кнопку напоминаний (отдельная строка)
    keyboard.append([
        InlineKeyboardButton(text="🆙 [ Напоминания ]", callback_data=f"category_reminder_mode_{category}")
    ])
    
    # Добавляем красивый заголовок категории
    keyboard.append([InlineKeyboardButton(text=f"────────── 📂 #{category} ──────────", callback_data="divider")])
    
    # Добавляем задачи категории
    if not filtered_tasks:
        keyboard.append([InlineKeyboardButton(text="📝 В этой категории нет задач", callback_data="divider")])
    else:
        for task_id, text, done, priority, reminder_time in filtered_tasks:
            status = "✅" if done else "☐"
            
            # Правильно инициализируем task_text
            task_text = status
            
            # Добавляем иконку приоритета ПОСЛЕ статуса
            if priority > 0:
                priority_icon = f"{priority_emoji.get(priority, '')}"
                task_text = f"{status}{priority_icon}"
            
            # Добавляем иконку напоминания
            if reminder_time:
                task_text = f"{task_text}🔔"
            
            # Добавляем текст задачи
            task_text = f"{task_text} {text}"
            
            keyboard.append([InlineKeyboardButton(text=task_text, callback_data=f"toggle_{task_id}")])
    
    keyboard.append([InlineKeyboardButton(text="↩️ Назад", callback_data="category_mode")])
    
    # Сохраняем текущий вид в context
    context.user_data['active_category_view'] = True
    if not hasattr(context, 'user_data'):
        context.user_data = {}
    context.user_data['active_category_view'] = True
    context.user_data['current_category'] = category
    context.user_data['current_view'] = {'type': 'category', 'category': category}
    
    message_text = f"Категория #{category}:"
    
    if query:
        await query.edit_message_text(text=message_text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text=message_text, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_reminders_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать меню напоминаний"""
    query = update.callback_query
    await query.answer()
    
    # Сбрасываем контекст категории при входе в общий режим напоминаний
    if not hasattr(context, 'user_data'):
        context.user_data = {}
    context.user_data['active_category_view'] = False
    context.user_data['current_category'] = ''

    if update.effective_chat.type in ['group', 'supergroup']:
        owner_id = update.effective_chat.id
    else:
        owner_id = update.effective_user.id if not query else query.from_user.id
    
    # Получаем все задачи пользователя
    tasks = get_tasks_db(owner_id, only_open=False)
    
    tasks_with_reminders = []
    tasks_without_reminders = []
    
    for task in tasks:
        task_id, text, done, priority, reminder_time = task
        if reminder_time:
            tasks_with_reminders.append(task)
        else:
            tasks_without_reminders.append(task)
    
    keyboard = []
    
    if tasks_with_reminders:
        keyboard.append([InlineKeyboardButton(text="С напоминаниями:", callback_data="divider")])
        for task_id, text, done, priority, reminder_time in tasks_with_reminders:
            status = "✅" if done else "☐"
            
            # Правильно инициализируем task_text
            task_text = status
            
            # Добавляем приоритет ПОСЛЕ статуса, потом напоминание
            if priority > 0:
                priority_icon = f"{priority_emoji.get(priority, '')}"
                task_text = f"{status}{priority_icon}"
            
            task_text = f"{task_text}🔔 {text}"
            
            keyboard.append([InlineKeyboardButton(
                text=task_text, 
                callback_data=f"reminder_options_{task_id}"
            )])
    
    if tasks_without_reminders:
        keyboard.append([InlineKeyboardButton(text="Без напоминаний:", callback_data="divider")])
        for task_id, text, done, priority, reminder_time in tasks_without_reminders:
            status = "✅" if done else "☐"
            
            # Правильно инициализируем task_text
            task_text = status
            
            # Добавляем приоритет ПОСЛЕ статуса
            if priority > 0:
                priority_icon = f"{priority_emoji.get(priority, '')}"
                task_text = f"{status}{priority_icon}"
            
            # Добавляем текст задачи
            task_text = f"{task_text} {text}"
            
            keyboard.append([InlineKeyboardButton(
                text=task_text, 
                callback_data=f"reminder_options_{task_id}"
            )])
    
    keyboard.append([InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_list")])
    
    total_with_reminders = len(tasks_with_reminders)
    total_without_reminders = len(tasks_without_reminders)
    
    await query.edit_message_text(
        text=f"🔔 Управление напоминаниями:\n\n"
             f"С напоминаниями: {total_with_reminders}\n"
             f"Без напоминаний: {total_without_reminders}\n\n"
             f"Выберите задачу для настройки напоминания:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_reminder_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать опции напоминания для задачи"""
    query = update.callback_query
    await query.answer()
    
    task_id = int(query.data.split('_')[2])
    
    # Проверяем, находимся ли мы в режиме категории
    back_callback = "reminder_mode"
    current_category = ''  # Инициализируем переменную заранее
    
    if hasattr(context, 'user_data') and context.user_data.get('active_category_view', False):
        # Получаем текущую категорию из callback_data
        current_category = context.user_data.get('current_category', '')
        back_callback = f"category_reminder_mode_{current_category}"

    keyboard = [
        [InlineKeyboardButton(text="🔕 Удалить напоминание", callback_data=f"delete_reminder_{task_id}")],
        [InlineKeyboardButton(text="🔔 30 минут", callback_data=f"snooze_reminder_{task_id}_30")],
        [InlineKeyboardButton(text="🔔 1 час", callback_data=f"snooze_reminder_{task_id}_60")],
        [InlineKeyboardButton(text="🔔 На завтра в это же время", callback_data=f"snooze_reminder_{task_id}_tomorrow")],
        [InlineKeyboardButton(text="🕐 Произвольное время", callback_data=f"custom_reminder_{task_id}")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data=back_callback)]
    ]
    
    await query.edit_message_text(
        text="🔔 Выберите действие с напоминанием:",
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
    if hasattr(context, 'user_data') and context.user_data.get('active_category_view', False):
        await show_category_reminder(update, context)  # ← ПРАВИЛЬНО!
    else:
        await show_reminders_menu(update, context)  # ← ПРАВИЛЬНО!

async def send_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Отправляет напоминание о задаче
    
    Args:
        context: Контекст бота с данными задачи
    """
    job = context.job
    task_id, owner_id, task_text = job.data
    
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
                text="🔔 Отложить на 1 час",
                callback_data=f"snooze_reminder_{task_id}_60"
            )
        ],
        [
            InlineKeyboardButton(
                text="📆 Отложить на завтра в это же время",
                callback_data=f"snooze_reminder_{task_id}_tomorrow"
            )
        ]
    ]
    
    await context.bot.send_message(
        chat_id=owner_id,
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
    logger.info(f"new reminder set for task {task_id}: {new_reminder}")
    
    # ВАЖНО: Очищаем reminder_task_id после завершения работы
    if 'reminder_task_id' in context.user_data:
        del context.user_data['reminder_task_id']
    
    await update.message.reply_text(
        f"⏰ Напоминание установлено на {new_reminder.strftime('%d.%m.%Y %H:%M')}",
        reply_markup=get_main_keyboard()
    )
    
    return ConversationHandler.END

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

async def show_category_priority(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать меню приоритетов для категории"""
    query = update.callback_query
    await query.answer()
    
    category = '_'.join(query.data.split('_')[3:])  # category_priority_mode_название_категории
    
    # Сохраняем текущую категорию в контексте
    if not hasattr(context, 'user_data'):
        context.user_data = {}
    context.user_data['current_category'] = category
    context.user_data['active_category_view'] = True

    if update.effective_chat.type in ['group', 'supergroup']:
        owner_id = update.effective_chat.id
    else:
        owner_id = query.from_user.id
    
    # Получаем задачи категории
    tasks = get_tasks_db(owner_id, only_open=False)
    from utils import extract_categories
    
    category_tasks = []
    for task in tasks:
        task_id, text, done, priority, reminder_time = task
        task_categories = extract_categories(text)
        if category in task_categories:
            category_tasks.append(task)
    
    keyboard = []
    # Добавляем красивый заголовок приоритетов для категории
    keyboard.append([InlineKeyboardButton(text=f"────────── 🔢 #{category} ──────────", callback_data="divider")])
    
    # Убираем группировку, показываем все задачи подряд
    for task_id, text, done, priority, reminder_time in category_tasks:
        # Определяем статус задачи
        status = "✅" if done else "☐"
        
        # Правильно инициализируем task_text
        task_text = status
        
        # Добавляем приоритет ПОСЛЕ статуса
        if priority > 0:
            priority_icon = f"{priority_emoji.get(priority, '')}"
            task_text = f"{status}{priority_icon}"
        
        # Добавляем текст задачи
        task_text = f"{task_text} {text}"
        
        keyboard.append([InlineKeyboardButton(
            text=task_text, 
            callback_data=f"set_priority_{task_id}"
        )])
    
    keyboard.append([InlineKeyboardButton(text="↩️ Назад", callback_data=f"filter_category_{category}")])
    
    await query.edit_message_text(
        text=f"🔢 Управление приоритетами в категории #{category}:\n\nВыберите задачу для изменения приоритета:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_category_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать напоминания для категории"""
    query = update.callback_query
    await query.answer()
    
    category = '_'.join(query.data.split('_')[3:])  # category_reminder_mode_название_категории

    # Сохраняем текущую категорию в контексте
    if not hasattr(context, 'user_data'):
        context.user_data = {}
    context.user_data['current_category'] = category
    context.user_data['active_category_view'] = True

    if update.effective_chat.type in ['group', 'supergroup']:
        owner_id = update.effective_chat.id
    else:
        owner_id = query.from_user.id
    
    # Получаем задачи категории с напоминаниями
    tasks = get_tasks_db(owner_id, only_open=False)
    from utils import extract_categories
    
    category_tasks_with_reminders = []
    category_tasks_without_reminders = []
    
    for task in tasks:
        task_id, text, done, priority, reminder_time = task
        task_categories = extract_categories(text)
        if category in task_categories:
            if reminder_time:
                category_tasks_with_reminders.append(task)
            else:
                category_tasks_without_reminders.append(task)
    
    keyboard = []
    # Добавляем красивый заголовок напоминаний для категории
    keyboard.append([InlineKeyboardButton(text=f"────────── 🔔 #{category} ──────────", callback_data="divider")])
    
    if category_tasks_with_reminders:
        keyboard.append([InlineKeyboardButton(text="🔔 С напоминаниями:", callback_data="divider")])
        for task_id, text, done, priority, reminder_time in category_tasks_with_reminders:
            status = "✅" if done else "☐"
            
            # Правильно инициализируем task_text
            task_text = status
            
            # Добавляем приоритет ПОСЛЕ статуса, потом напоминание
            if priority > 0:
                priority_icon = f"{priority_emoji.get(priority, '')}"
                task_text = f"{status}{priority_icon}"
            
            task_text = f"{task_text}🔔 {text}"
            
            keyboard.append([InlineKeyboardButton(
                text=task_text, 
                callback_data=f"reminder_options_{task_id}"
            )])
    
    if category_tasks_without_reminders:
        keyboard.append([InlineKeyboardButton(text="📝 Без напоминаний:", callback_data="divider")])
        for task_id, text, done, priority, reminder_time in category_tasks_without_reminders:
            status = "✅" if done else "☐"
            
            # Правильно инициализируем task_text
            task_text = status
            
            # Добавляем приоритет ПОСЛЕ статуса
            if priority > 0:
                priority_icon = f"{priority_emoji.get(priority, '')}"
                task_text = f"{status}{priority_icon}"
            
            # Добавляем текст задачи
            task_text = f"{task_text} {text}"
            
            keyboard.append([InlineKeyboardButton(
                text=task_text, 
                callback_data=f"reminder_options_{task_id}"
            )])
    
    keyboard.append([InlineKeyboardButton(text="↩️ Назад", callback_data=f"filter_category_{category}")])
    
    total_with_reminders = len(category_tasks_with_reminders)
    total_without_reminders = len(category_tasks_without_reminders)
    
    await query.edit_message_text(
        text=f"🔔 Напоминания в категории #{category}:\n\n"
             f"С напоминаниями: {total_with_reminders}\n"
             f"Без напоминаний: {total_without_reminders}\n\n"
             f"Выберите задачу для настройки напоминания:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
async def toggle_all_category_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Переключить статус всех задач в категории"""
    query = update.callback_query
    await query.answer()
    
    category = '_'.join(query.data.split('_')[3:])  # toggle_all_category_название_категории
    
    if update.effective_chat.type in ['group', 'supergroup']:
        owner_id = update.effective_chat.id
    else:
        owner_id = query.from_user.id
    
    # Получаем задачи категории
    tasks = get_tasks_db(owner_id, only_open=False)
    from utils import extract_categories
    
    category_tasks = []
    for task in tasks:
        task_id, text, done, priority, reminder_time = task
        task_categories = extract_categories(text)
        if category in task_categories:
            category_tasks.append(task)
    
    if not category_tasks:
        await query.answer("В этой категории нет задач")
        return
    
    # Определяем новый статус (если есть незавершенные - завершаем все, иначе - снимаем завершение со всех)
    has_incomplete = any(not task[2] for task in category_tasks)
    new_status = 1 if has_incomplete else 0
    
    # Обновляем статус всех задач категории
    for task_id, text, done, priority, reminder_time in category_tasks:
        toggle_task_status_db(task_id, new_status)
    
    # Возвращаемся к просмотру категории
    await show_tasks_by_category(update, context)

async def start_custom_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    task_id = int(query.data.split('_')[2])
    context.user_data['reminder_task_id'] = task_id
    
    await query.edit_message_text(
        text="🕐 Введите время напоминания в формате:\n\n"
             "• 15:30 - сегодня в 15:30\n"
             "• 29.05 10:00 - 29 мая в 10:00\n"
             "• завтра 09:00 - завтра в 09:00\n\n",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Отмена", callback_data="back_to_list")]
        ])  # ✅ ПРАВИЛЬНО: inline-клавиатура
    )
    
    return SETTING_CUSTOM_REMINDER

async def save_custom_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохранить произвольное время напоминания"""
    if update.effective_chat.type in ['group', 'supergroup']:
        owner_id = update.effective_chat.id
    else:
        owner_id = update.effective_user.id
    
    input_text = update.message.text.strip()
    
    if input_text == "/cancel":
        await update.message.reply_text(
            "❌ Установка напоминания отменена.",
            reply_markup=get_main_keyboard()
        )
        return ConversationHandler.END
    
    # Используем функцию из utils для парсинга времени
    from utils import extract_reminder_time
    reminder_time, _ = extract_reminder_time(input_text)
    
    if not reminder_time:
        await update.message.reply_text(
            "❌ Неверный формат времени. Попробуйте еще раз:\n\n"
            "• 15:30 - сегодня в 15:30\n"
            "• 29.05 10:00 - 29 мая в 10:00\n"
            "• завтра 09:00 - завтра в 09:00"
        )
        return SETTING_CUSTOM_REMINDER
    
    task_id = context.user_data.get('reminder_task_id')
    if not task_id:
        await update.message.reply_text(
            "❌ Ошибка: задача не найдена.",
            reply_markup=get_main_keyboard()
        )
        return ConversationHandler.END
    
    # Устанавливаем напоминание
    set_reminder(task_id, reminder_time)
    
    await update.message.reply_text(
        f"✅ Напоминание установлено на {reminder_time.strftime('%d.%m.%Y %H:%M')}",
        reply_markup=get_main_keyboard()
    )
    
    # Возвращаемся к списку задач
    if hasattr(context, 'user_data') and context.user_data.get('active_category_view', False):
        await show_tasks_by_category(update, context)
    else:
        await list_tasks(update, context)
    
    return ConversationHandler.END

# Константы для поддержки
PAYMENTS_TOKEN = os.getenv("PAYMENTS_TOKEN", "381764678:TEST:100037")
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY")

async def support_developer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать меню поддержки разработчика с вариантами донатов"""
    logger.info("support_developer function called!")
    
    user_id = update.effective_user.id
    user_donations = get_user_donations_db(user_id)
    total_amount, total_count = get_total_donations_db()
    
    keyboard = [
        [InlineKeyboardButton("100₽ - ☕", callback_data="donate_100")],
        [InlineKeyboardButton("300₽ - 🍕", callback_data="donate_300")],
        [InlineKeyboardButton("1000₽ - 💪", callback_data="donate_1000")],
        [InlineKeyboardButton("💰 Другая сумма", callback_data="donate_custom")]
    ]
    
    message_text = "🌟 **Поддержи проект!**\n\n"
    message_text += "Этот бот создан с любовью и полностью бесплатен. "
    message_text += "Если он помогает тебе организовать дела, буду благодарен за поддержку! 🫶\n\n"
    
    if user_donations > 0:
        message_text += f"💖 Твои донаты: **{user_donations}₽**\n"

    message_text += "\n\n_Спасибо за поддержку!_ 🙏"
    
    await update.message.reply_text(
        message_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def handle_donation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка нажатий на кнопки донатов"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "donate_custom":
        await query.edit_message_text(
            "🤗 Введи свою сумму от 100₽ до 15000₽\n\n",
            parse_mode="Markdown"
        )
        context.user_data["waiting_custom_amount"] = True
        return
    
    if data == "cancel_payment":
        context.user_data.pop('donation_amount', None)
        await query.edit_message_text("❌ Оплата отменена")
        return
    
    if data.startswith("payment_"):
        parts = data.split("_")
        payment_method = parts[1]  # card или sbp
        amount = int(parts[2])
        
        await send_donation_invoice(query, context, amount, payment_method)
        return
    
    # Обработка фиксированных сумм
    amount_map = {"donate_100": 100, "donate_300": 300, "donate_1000": 1000}
    amount = amount_map.get(data)
    if not amount:
        return
    
    await show_payment_methods(query, context, amount)

async def send_donation_invoice(query_or_update, context: ContextTypes.DEFAULT_TYPE, amount: int, payment_method: str = "card") -> None:
    """Отправляет ссылку на оплату через ЮKassa"""
    
    if hasattr(query_or_update, 'from_user'):
        user_id = query_or_update.from_user.id
    else:
        user_id = query_or_update.effective_user.id
    
    payment = create_yookassa_payment(amount, payment_method, user_id)
    
    if not payment:
        error_text = "❌ Извините, произошла ошибка при создании платежа. Попробуйте позже."
        if hasattr(query_or_update, 'edit_message_text'):
            await query_or_update.edit_message_text(error_text)
        else:
            await query_or_update.message.reply_text(error_text)
        return
    
    payment_url = payment.get('confirmation', {}).get('confirmation_url')
    
    if not payment_url:
        error_text = "❌ Не удалось получить ссылку на оплату. Попробуйте позже."
        if hasattr(query_or_update, 'edit_message_text'):
            await query_or_update.edit_message_text(error_text)
        else:
            await query_or_update.message.reply_text(error_text)
        return
    
    method_text = "💳 Банковской картой" if payment_method == "card" else "📱 Через СБП"
    
    keyboard = [
        [InlineKeyboardButton("💰 Перейти к оплате", url=payment_url)],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_payment")]
    ]
    
    text = (
        f"💝 **Спасибо за желание поддержать проект!**\n\n"
        f"💰 Сумма: **{amount}₽**\n"
        f"💳 Способ: {method_text}\n\n"
        f"Нажмите кнопку ниже для перехода к оплате:"
    )
    
    if hasattr(query_or_update, 'edit_message_text'):
        await query_or_update.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    else:
        await query_or_update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

async def handle_custom_donation_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает ввод произвольной суммы пожертвования"""
    if not context.user_data.get('waiting_custom_amount'):
        return
    
    try:
        amount = int(update.message.text.strip())
        
        if amount < 100:
            await update.message.reply_text(
                "⚠️ Минимальная сумма поддержки: 100₽\n\n"
                "Это ограничение платежной системы.\n"
                "Попробуйте ввести другую сумму:"
            )
            return
        
        if amount > 15000:
            await update.message.reply_text(
                "Максимальная сумма поддержки: 15000₽\n"
                "Попробуйте ввести другую сумму:"
            )
            return
        
        context.user_data['waiting_custom_amount'] = False
        context.user_data['donation_amount'] = amount
        
        await show_payment_methods(update, context, amount)
        
    except ValueError:
        await update.message.reply_text(
            "Пожалуйста, введите корректную сумму числом.\n"
            "Например: 500"
        )
async def pre_checkout_donation_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик предварительной проверки пожертвования"""
    query = update.pre_checkout_query
    
    # Проверяем, что это пожертвование
    if not query.invoice_payload.startswith("donation_"):
        await query.answer(ok=False, error_message="Ошибка в данных платежа")
        return
    
    # Подтверждаем платеж
    await query.answer(ok=True)
    logger.info(f"Pre-checkout approved for donation from user {query.from_user.id}")

async def successful_donation_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик успешного пожертвования"""
    payment = update.message.successful_payment
    user_id = update.effective_user.id
    
    # Извлекаем сумму из payload
    amount = int(payment.invoice_payload.split("_")[1])
    
    # Записываем пожертвование в базу данных
    add_donation_db(
        user_id=user_id,
        amount=amount,
        payment_id=payment.telegram_payment_charge_id
    )
    
    # Получаем обновленную статистику
    user_total = get_user_donations_db(user_id)
    
    await update.message.reply_text(
        f"💙 **Огромное спасибо за поддержку!**\n\n"
        f"Ваше пожертвование **{amount}₽** получено.\n"
        f"Общая ваша поддержка: **{user_total}₽**\n\n"
        f"Благодаря таким пользователям как вы, проект продолжает развиваться!\n\n"
        f"🙏 Вы помогаете делать бот лучше для всех!",
        reply_markup=get_main_keyboard(),
        parse_mode='Markdown'
    )
    
    logger.info(f"Successful donation: user_id={user_id}, amount={amount}₽, payment_id={payment.telegram_payment_charge_id}")

async def show_payment_methods(update, context: ContextTypes.DEFAULT_TYPE, amount: int) -> None:
    """Показывает способы оплаты"""
    keyboard = [
        [InlineKeyboardButton("💳 Банковской картой", callback_data=f"payment_card_{amount}")],
        [InlineKeyboardButton("📱 СБП (Быстрые платежи)", callback_data=f"payment_sbp_{amount}")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_payment")]
    ]
    
    text = (
        f"💰 **Сумма: {amount}₽**\n\n"
        "Выберите способ оплаты:\n\n"
        "💳 **Банковская карта** - обычная оплата картой\n"
        "📱 **СБП** - быстрая оплата через приложение банка"
    )
    
    if hasattr(update, 'message'):
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await update.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

def create_yookassa_payment(amount: int, payment_method: str, user_id: int) -> dict:
    """Создает платеж через ЮKassa API"""
    
    logger.info(f"Creating YooKassa payment: amount={amount}, method={payment_method}, user_id={user_id}")
    logger.info(f"YOOKASSA_SHOP_ID: {'SET' if YOOKASSA_SHOP_ID else 'NOT SET'}")
    logger.info(f"YOOKASSA_SECRET_KEY: {'SET' if YOOKASSA_SECRET_KEY else 'NOT SET'}")
    
    # Проверяем наличие учетных данных ЮKassa
    if not YOOKASSA_SHOP_ID or not YOOKASSA_SECRET_KEY:
        logger.error("YooKassa credentials not configured")
        return None
    
    credentials = f"{YOOKASSA_SHOP_ID}:{YOOKASSA_SECRET_KEY}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    
    headers = {
        'Authorization': f'Basic {encoded_credentials}',
        'Idempotence-Key': str(uuid.uuid4()),
        'Content-Type': 'application/json'
    }
    
    payment_data = {
        "amount": {
            "value": f"{amount}.00",
            "currency": "RUB"
        },
        "confirmation": {
            "type": "redirect",
            "return_url": f"https://t.me/PocketToDoBot"
        },
        "capture": True,
        "description": f"Поддержка проекта - {amount}₽",
        "receipt": {
            "customer": {
                "email": "support@example.com"
            },
            "items": [
                {
                    "description": "Поддержка проекта",
                    "quantity": "1.00",
                    "amount": {
                        "value": f"{amount}.00",
                        "currency": "RUB"
                    },
                    "vat_code": 1,
                    "payment_mode": "full_payment",
                    "payment_subject": "service"
                }
            ]
        },
        "metadata": {
            "user_id": str(user_id)
        }
    }
    
    if payment_method == "sbp":
        payment_data["payment_method_data"] = {
            "type": "sbp"
        }
    
    # ДОБАВЛЯЕМ НЕДОСТАЮЩУЮ ЧАСТЬ:
    try:
        logger.info(f"Sending request to YooKassa API...")
        response = requests.post(
            'https://api.yookassa.ru/v3/payments',
            headers=headers,
            json=payment_data,
            timeout=30
        )
        
        logger.info(f"YooKassa API response: {response.status_code}")
        
        if response.status_code == 200:
            payment_result = response.json()
            logger.info(f"Payment created successfully: {payment_result.get('id')}")
            return payment_result
        else:
            logger.error(f"YooKassa API error: {response.status_code}, {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Error creating YooKassa payment: {e}")
        return None
