from typing import List, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from database import get_tasks_db

priority_emoji = {
    3: "🔴", # Высокий
    2: "🟡", # Средний
    1: "🔵"  # Низкий
}

def get_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            ["📋 Мои задачи"],
            ["🧹 Удалить выполненные"],
            ["🫶 Поддержи проект"]
        ], 
        resize_keyboard=True
    )

def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [["❌ Отмена"]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_task_list_markup(owner_id: int) -> Optional[InlineKeyboardMarkup]:
    tasks = get_tasks_db(owner_id, only_open=False)
    keyboard = []
    
    total = len(tasks)
    done_count = sum(1 for task in tasks if task[2])
    
    # Добавляем кнопку статуса выполнения (отдельная строка)
    keyboard.append([
        InlineKeyboardButton(text=f"🔄 [ {done_count}/{total} ] [ Отметить все ]", callback_data="toggle_all")
    ])
    
    # Добавляем кнопку категорий (отдельная строка)
    keyboard.append([
        InlineKeyboardButton(text="#️⃣ [ Категории ]", callback_data="category_mode")
    ])
    
    # Добавляем кнопку приоритетов (отдельная строка)
    keyboard.append([
        InlineKeyboardButton(text="🔢 [ Приоритет ]", callback_data="priority_mode")
    ])
    
    # Добавляем кнопку напоминаний (отдельная строка)
    keyboard.append([
        InlineKeyboardButton(text="🆙 [ Напоминания ]", callback_data="reminder_mode")
    ])
    
    # Добавляем красивый заголовок "Мои задачи"
    keyboard.append([InlineKeyboardButton(text="────────── 📋 Мои задачи ──────────", callback_data="divider")])
    
    # Добавляем задачи
    for task_id, text, done, priority, reminder_time in tasks:
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
        
        keyboard.append([
            InlineKeyboardButton(text=task_text, callback_data=f"toggle_{task_id}"),
        ])
    
    return InlineKeyboardMarkup(keyboard) if keyboard else None


