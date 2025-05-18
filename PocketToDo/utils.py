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
    'высокий': 3, 'высокаЯ': 3, 'важно': 3, 'красный': 3, 'срочно': 3,
    'средний': 2, 'среднЯЯ': 2, 'среднее': 2, 'средне': 2, 'желтый': 2, 'жЮлтый': 2,
    'низкий': 1, 'низкаЯ': 1, 'низко': 1, 'синий': 1
}

def extract_priority(text: str) -> Tuple[int, str]:
    logger.info(f"Обработка текста для определения приоритета: '{text}'")
    match = re.search(r'!(\w+)', text, re.IGNORECASE)
    if not match:
        logger.info("Приоритет не найден")
        return 0, text
    priority_text = match.group(1).lower()
    logger.info(f"Найден приоритет: {priority_text}")
    priority = priority_map.get(priority_text, 0)
    clean_text = re.sub(r'!\w+', '', text).strip()
    logger.info(f"Установлен приоритет: {priority}, очищенный текст: '{clean_text}'")
    return priority, clean_text
