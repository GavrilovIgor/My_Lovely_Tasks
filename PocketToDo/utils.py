import re
import logging
from datetime import datetime, timedelta, timezone
from typing import Tuple, List, Optional

logger = logging.getLogger(__name__)

def extract_reminder_time(text: str) -> Tuple[Optional[datetime], str]:
    logger.info(f"extract_reminder_time called with text: '{text}'")
    
    try:
        now = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=3)))
        
        # Словарь дней недели
        weekdays = {
            'понедельник': 0, 'пн': 0,
            'вторник': 1, 'вт': 1,
            'среда': 2, 'ср': 2, 'среду': 2,
            'четверг': 3, 'чт': 3,
            'пятница': 4, 'пт': 4, 'пятницу': 4,
            'суббота': 5, 'сб': 5, 'субботу': 5,
            'воскресенье': 6, 'вс': 6
        }
        
        # Паттерн для дня недели с временем (понедельник 09:00)
        weekday_pattern = '|'.join(weekdays.keys())
        match = re.search(rf'({weekday_pattern})\s+(\d{{1,2}}):(\d{{2}})', text, re.IGNORECASE)
        if match:
            logger.info(f"Found weekday with time pattern: {match.group(0)}")
            weekday_name = match.group(1).lower()
            hour = int(match.group(2))
            minute = int(match.group(3))
            
            target_weekday = weekdays[weekday_name]
            current_weekday = now.weekday()
            
            # Вычисляем количество дней до нужного дня недели
            days_ahead = target_weekday - current_weekday
            if days_ahead <= 0:  # Если день уже прошел на этой неделе или сегодня
                days_ahead += 7  # Берем следующую неделю
            
            target_date = now + timedelta(days=days_ahead)
            reminder_time = datetime(target_date.year, target_date.month, target_date.day, 
                                   hour, minute, tzinfo=timezone(timedelta(hours=3)))
            
            clean_text = re.sub(rf'({weekday_pattern})\s+(\d{{1,2}}):(\d{{2}})', '', text, flags=re.IGNORECASE).strip()
            logger.info(f"Weekday reminder time set to: {reminder_time}")
            return reminder_time, clean_text
        
        # Паттерн для дня недели без времени (понедельник) - по умолчанию 09:00
        match = re.search(rf'\b({weekday_pattern})\b', text, re.IGNORECASE)
        if match:
            logger.info(f"Found weekday only pattern: {match.group(0)}")
            weekday_name = match.group(1).lower()
            
            target_weekday = weekdays[weekday_name]
            current_weekday = now.weekday()
            
            # Вычисляем количество дней до нужного дня недели
            days_ahead = target_weekday - current_weekday
            if days_ahead <= 0:  # Если день уже прошел на этой неделе или сегодня
                days_ahead += 7  # Берем следующую неделю
            
            target_date = now + timedelta(days=days_ahead)
            reminder_time = datetime(target_date.year, target_date.month, target_date.day, 
                                   9, 0, tzinfo=timezone(timedelta(hours=3)))  # По умолчанию 09:00
            
            clean_text = re.sub(rf'\b({weekday_pattern})\b', '', text, flags=re.IGNORECASE).strip()
            logger.info(f"Weekday-only reminder time set to: {reminder_time} (default 09:00)")
            return reminder_time, clean_text
        
        # Паттерн для даты и времени (29.05 10:00)
        match = re.search(r'(\d{1,2})\.(\d{1,2})\s+(\d{1,2}):(\d{2})', text)
        if match:
            logger.info(f"Found date pattern: {match.group(0)}")
            day = int(match.group(1))
            month = int(match.group(2))
            hour = int(match.group(3))
            minute = int(match.group(4))
            year = now.year
            
            try:
                reminder_time = datetime(year, month, day, hour, minute, tzinfo=timezone(timedelta(hours=3)))
                if reminder_time < now:
                    reminder_time = datetime(year + 1, month, day, hour, minute, tzinfo=timezone(timedelta(hours=3)))
            except ValueError as e:
                logger.error(f"Invalid date in reminder: {e}")
                return None, text
            
            clean_text = re.sub(r'(\d{1,2})\.(\d{1,2})\s+(\d{1,2}):(\d{2})', '', text).strip()
            logger.info(f"Reminder time set to: {reminder_time}")
            return reminder_time, clean_text
        
        # Паттерн для "завтра ЧЧ:ММ"
        match = re.search(r'завтра\s+(\d{1,2}):(\d{2})', text, re.IGNORECASE)
        if match:
            logger.info(f"Found 'tomorrow' pattern: {match.group(0)}")
            hour = int(match.group(1))
            minute = int(match.group(2))
            
            reminder_time = datetime(now.year, now.month, now.day, hour, minute, tzinfo=timezone(timedelta(hours=3)))
            reminder_time = reminder_time + timedelta(days=1)
            
            clean_text = re.sub(r'завтра\s+(\d{1,2}):(\d{2})', '', text, flags=re.IGNORECASE).strip()
            logger.info(f"Tomorrow reminder time set to: {reminder_time}")
            return reminder_time, clean_text
        
        # Паттерн для "сегодня ЧЧ:ММ"
        match = re.search(r'сегодня\s+(\d{1,2}):(\d{2})', text, re.IGNORECASE)
        if match:
            logger.info(f"Found 'today' pattern: {match.group(0)}")
            hour = int(match.group(1))
            minute = int(match.group(2))
            
            reminder_time = datetime(now.year, now.month, now.day, hour, minute, tzinfo=timezone(timedelta(hours=3)))
            if reminder_time < now:
                reminder_time = reminder_time + timedelta(days=1)
            
            clean_text = re.sub(r'сегодня\s+(\d{1,2}):(\d{2})', '', text, flags=re.IGNORECASE).strip()
            logger.info(f"Today reminder time set to: {reminder_time}")
            return reminder_time, clean_text
        
        # Паттерн для времени без даты (ЧЧ:ММ)
        match = re.search(r'(\d{1,2}):(\d{2})', text)
        if match:
            logger.info(f"Found time-only pattern: {match.group(0)}")
            hour = int(match.group(1))
            minute = int(match.group(2))
            
            reminder_time = datetime(now.year, now.month, now.day, hour, minute, tzinfo=timezone(timedelta(hours=3)))
            if reminder_time < now:
                reminder_time = reminder_time + timedelta(days=1)
            
            clean_text = re.sub(r'(\d{1,2}):(\d{2})', '', text).strip()
            logger.info(f"Time-only reminder set to: {reminder_time}")
            return reminder_time, clean_text
        
        logger.info("No time pattern found at all")
        return None, text
        
    except Exception as e:
        logger.error(f"Unexpected error in extract_reminder_time: {e}")
        return None, text


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
