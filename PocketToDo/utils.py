import re
import logging
from datetime import datetime, timedelta, timezone
from typing import Tuple, List, Optional

logger = logging.getLogger(__name__)

def extract_reminder_time(text: str) -> Tuple[Optional[datetime], str]:
    logger.info(f"Обработка текста для напоминания: '{text}'")
    match = re.search(r'@(\d{1,2}):(\d{2})', text)
    if not match:
        logger.info("Напоминание не найдено")
        return None, text
    hour = int(match.group(1))
    minute = int(match.group(2))
    logger.info(f"Найдено время: {hour}:{minute}")
    clean_text = re.sub(r'@\d{1,2}:\d{2}', '', text).strip()
    now = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=3)))
    reminder_time = datetime(now.year, now.month, now.day, hour, minute, tzinfo=timezone(timedelta(hours=3)))
    if reminder_time < now:
        reminder_time = reminder_time + timedelta(days=1)
    logger.info(f"Установлено напоминание на: {reminder_time}")
    return reminder_time, clean_text

def extract_categories(text: str) -> List[str]:
    hashtags = re.findall(r'#(\w+)', text)
    return hashtags

priority_map = {
    # Высокий приоритет
    'высокий': 3, 'высокая': 3, 'важно': 3, 'важная': 3, 'главное': 3, 'главная': 3,
    'срочно': 3, 'срочная': 3, 'красный': 3, '🔥': 3, '‼️': 3, 'немедленно': 3,
    'urgent': 3, 'top': 3, 'critical': 3, 'критично': 3, 'must': 3, 'mustdo': 3, 'must-do': 3,
    'первоочередно': 3, 'первоочередная': 3, 'первоочередный': 3, 'важнейшее': 3, 'asap': 3,
    '1': 3, 'срочно!': 3, '1!': 3, # поддержка "! 1" и "!1"

    # Средний приоритет
    'средний': 2, 'средняя': 2, 'среднее': 2, 'средне': 2, 'желтый': 2, 'жёлтый': 2,
    'yellow': 2, 'обычно': 2, 'обычная': 2, 'обычный': 2, 'можно позже': 2, 'можно_позже': 2,
    'можно-позже': 2, 'не срочно': 2, 'несрочно': 2, 'regular': 2, 'стандарт': 2, 'стандартная': 2,
    '2': 2, 'средне!': 2, '2!': 2, # поддержка "! 2" и "!2"

    # Низкий приоритет
    'низкий': 1, 'низкая': 1, 'низко': 1, 'синий': 1, 'blue': 1, 'отложить': 1,
    'неважно': 1, 'неважная': 1, 'optional': 1, 'опционально': 1, 'можно не делать': 1,
    'можно_не_делать': 1, 'можно-не-делать': 1, 'когда-нибудь': 1, 'someday': 1,
    'потом': 1, 'later': 1, 'не спешно': 1, 'несрочная': 1, 'несрочный': 1,
    '3': 1, 'низко!': 1, '3!': 1 # поддержка "! 3" и "!3"
}

def extract_priority(text: str) -> Tuple[int, str]:
    logger.info(f"Обработка текста для определения приоритета: '{text}'")
    # Теперь ищем как '!важно', '! важно', '! 1', '!1' и т.д.
    match = re.search(r'!\s*([\w\d]+)', text, re.IGNORECASE)
    if not match:
        logger.info("Приоритет не найден")
        return 0, text
    priority_text = match.group(1).lower()
    logger.info(f"Найден приоритет: {priority_text}")
    priority = priority_map.get(priority_text, 0)
    # Удаляем из текста как '!важно', так и '! важно', '! 1', '!1'
    clean_text = re.sub(r'!\s*[\w\d]+', '', text).strip()
    logger.info(f"Установлен приоритет: {priority}, очищенный текст: '{clean_text}'")
    return priority, clean_text
