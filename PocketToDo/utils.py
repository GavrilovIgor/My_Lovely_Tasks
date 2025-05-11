import re
import logging
from datetime import datetime, timedelta
from typing import Tuple, List, Optional

logger = logging.getLogger(__name__)

def extract_reminder_time(text: str) -> Tuple[Optional[datetime], str]:
    """
    Извлекает время напоминания из текста задачи
    
    Args:
        text: Текст задачи с возможным напоминанием в формате @ЧЧ:ММ
        
    Returns:
        Tuple с временем напоминания (или None) и очищенным текстом
    """
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

def extract_categories(text: str) -> List[str]:
    """
    Извлекает хэштеги (категории) из текста задачи
    
    Args:
        text: Текст задачи с возможными хэштегами
        
    Returns:
        Список найденных категорий
    """
    hashtags = re.findall(r'#(\w+)', text)
    return hashtags
