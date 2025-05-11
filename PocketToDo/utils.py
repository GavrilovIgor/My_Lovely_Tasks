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

def extract_priority(text: str) -> Tuple[int, str]:
    """
    Извлекает приоритет из текста задачи
    
    Args:
        text: Текст задачи с возможным указанием приоритета (!высокий, !средний, !низкий)
        
    Returns:
        Tuple с приоритетом (3-высокий, 2-средний, 1-низкий, 0-не указан) и очищенным текстом
    """
    logger.info(f"Обработка текста для определения приоритета: '{text}'")
    
    # Словарь соответствия текстовых приоритетов числовым
    priority_map = {
    'высокий': 3,
    'высокая': 3,
    'важно': 3,
    'красный': 3,
    'срочно': 3,
    'средний': 2,
    'средняя': 2,
    'среднее': 2,
    'средне': 2,
    'желтый': 2,
    'жёлтый': 2,
    'низкий': 1,
    'низкая': 1,
    'низко': 1,
    'синий': 1
}
    
    # Ищем приоритет в формате !приоритет
    match = re.search(r'!(\w+)', text, re.IGNORECASE)
    if not match:
        logger.info("Приоритет не найден")
        return 0, text
    
    priority_text = match.group(1).lower()
    logger.info(f"Найден приоритет: {priority_text}")
    
    # Определяем числовой приоритет
    priority = priority_map.get(priority_text, 0)
    
    # Удаляем приоритет из текста
    clean_text = re.sub(r'!\w+', '', text).strip()
    
    logger.info(f"Установлен приоритет: {priority}, очищенный текст: '{clean_text}'")
    return priority, clean_text

