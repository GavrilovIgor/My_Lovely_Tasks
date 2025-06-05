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
            ["🧹 Удалить выполненные"]
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
    keyboard.append([
        InlineKeyboardButton(
            text=f"🔄 [ {done_count}/{total} выполнено ]",
            callback_data="toggle_all"
        )
    ])
    keyboard.append([InlineKeyboardButton(text=f"#️⃣ [ Категории ]", callback_data="category_mode")])
    keyboard.append([InlineKeyboardButton(text=f"🔢 [ Определить приоритет ]", callback_data="priority_mode")])
    keyboard.append([InlineKeyboardButton(text=f"🆙 [ Напоминания ]", callback_data="reminder_mode")])
    keyboard.append([InlineKeyboardButton(text="─" * 25, callback_data="divider")])


    for task_id, text, done, priority, reminder_time in tasks:
        status = "✅" if done else "☐"
        task_text = f"{status} "
        if priority > 0:
            priority_icon = priority_emoji.get(priority, "")
            task_text += f"{priority_icon} "
        if reminder_time:
            task_text += f"🔔 "
        task_text += text
        keyboard.append([
            InlineKeyboardButton(
                text=task_text,
                callback_data=f"toggle_{task_id}",
            )
        ])
    return InlineKeyboardMarkup(keyboard) if keyboard else None
