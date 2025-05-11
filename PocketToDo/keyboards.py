from typing import List, Dict, Optional, Any, Tuple
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

from database import get_tasks_db

def get_main_keyboard() -> ReplyKeyboardMarkup:
    """
    Создает основную клавиатуру бота
    
    Returns:
        ReplyKeyboardMarkup: Клавиатура с основными кнопками
    """
    return ReplyKeyboardMarkup(
        [
            ["📋 Мои задачи"],
            ["🧹 Удалить выполненные"]
        ], 
        resize_keyboard=True
    )

def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """
    Создает клавиатуру с кнопкой отмены
    
    Returns:
        ReplyKeyboardMarkup: Клавиатура с кнопкой отмены
    """
    return ReplyKeyboardMarkup(
        [["❌ Отмена"]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_task_list_markup(user_id: int) -> Optional[InlineKeyboardMarkup]:
    """
    Создает разметку для списка задач пользователя
    
    Args:
        user_id: ID пользователя
        
    Returns:
        InlineKeyboardMarkup или None, если у пользователя нет задач
    """
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
    
    # Кнопки управления - делаем кнопку категорий более заметной
    keyboard.append([
        InlineKeyboardButton(
            text=f"#️⃣ [ Категории ]",
            callback_data="category_mode"
        )
    ])
    
    keyboard.append([
        InlineKeyboardButton(
            text=f"🔢 [ Определить приоритет ]",
            callback_data="priority_mode"
        )
    ])
    
    keyboard.append([
        InlineKeyboardButton(
            text=f"🆙 [ Напоминания ]",
            callback_data="reminder_mode"
        )
    ])
    
    # Разделитель
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
        # Формируем текст задачи
        status = "✅" if done else "☐"
        task_text = f"{status} "
        
        # Добавляем приоритет если он установлен
        if priority > 0:
            priority_icon = priority_emoji.get(priority, "")
            task_text += f"{priority_icon} "
        
        # Добавляем индикатор напоминания
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
