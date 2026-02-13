from datetime import datetime, timedelta
from utils.html_parser import fetch_html_content, parse_pravoslavie_calendar_page, parse_azbyka_calendar_page

# core/calendar_data.py
# Этот файл будет хранить кэшированные данные православного календаря.

cached_calendar_data = {}
PRAVOSLAVIE_BASE_URL = "https://days.pravoslavie.ru/Days/"
AZBYKA_BASE_URL = "https://azbyka.ru/days/"

def convert_new_style_to_old_style(date_obj: datetime) -> datetime:
    """
    Конвертирует дату из нового стиля в старый стиль.
    Разница между стилями зависит от века.
    """
    year = date_obj.year
    if 1582 <= year <= 1699:
        delta = 10
    elif 1700 <= year <= 1799:
        delta = 11
    elif 1800 <= year <= 1899:
        delta = 12
    elif 1900 <= year <= 2099:
        delta = 13
    elif 2100 <= year <= 2199:
        delta = 14
    else:
        # Для дат вне этих диапазонов, используем дельту 13 как наиболее распространенную
        delta = 13 
    
    return date_obj - timedelta(days=delta)

async def fetch_and_cache_calendar_data(date_str: str):
    """
    Извлекает данные календаря с azbyka.ru, а затем с pravoslavie.ru (если необходимо) и кэширует их.
    date_str должен быть в формате 'YYYYMMDD'.
    """
    year = int(date_str[:4])
    month = int(date_str[4:6])
    day = int(date_str[6:])
    
    current_date_obj = datetime(year, month, day)
    
    # Попытка получить данные с azbyka.ru (всегда по новому стилю)
    azbyka_url = f"{AZBYKA_BASE_URL}{year}-{month:02d}-{day:02d}/"
    azbyka_html_content = await fetch_html_content(azbyka_url)
    
    final_calendar_data = {
        "holidays": [],
        "namedays": [],
        "fasting": "Информация о посте не найдена.",
        "week_info": "Информация о седмице не найдена.",
        "image_url": None,
        "theophan_thoughts": []
    }

    if azbyka_html_content:
        azbyka_data = parse_azbyka_calendar_page(azbyka_html_content)
        if azbyka_data and (azbyka_data["holidays"] or azbyka_data["namedays"] or azbyka_data["fasting"] != "Поста нет." or azbyka_data["week_info"]):
            final_calendar_data.update(azbyka_data)
            print(f"INFO: Данные получены из Azbyka.ru для {date_str}")
    
    # Всегда пытаемся получить данные с pravoslavie.ru для дополнения (theophan_thoughts и др.)
    # image_url с pravoslavie.ru не используем — избегаем претензий по авторским правам
    old_style_date_obj = convert_new_style_to_old_style(current_date_obj)
    old_style_date_str = old_style_date_obj.strftime("%Y%m%d")
    pravoslavie_new_style_equivalent_url = f"{PRAVOSLAVIE_BASE_URL}{old_style_date_str}.html"
    pravoslavie_new_style_equivalent_html_content = await fetch_html_content(pravoslavie_new_style_equivalent_url)

    if not azbyka_html_content and not pravoslavie_new_style_equivalent_html_content:
        print(f"ERROR: Не удалось получить данные календаря для {date_str} (оба источника недоступны).")
        return None

    if pravoslavie_new_style_equivalent_html_content:
        pravoslavie_data = parse_pravoslavie_calendar_page(pravoslavie_new_style_equivalent_html_content)
        if pravoslavie_data:
            # Приоритет для theophan_thoughts из pravoslavie.ru (image_url не берём)
            if pravoslavie_data.get("theophan_thoughts"):
                final_calendar_data["theophan_thoughts"] = pravoslavie_data["theophan_thoughts"]
            
            # Дополняем остальные поля, если они не были заполнены Azbyka
            if not final_calendar_data["holidays"] and pravoslavie_data["holidays"]:
                final_calendar_data["holidays"] = pravoslavie_data["holidays"]
            if not final_calendar_data["namedays"] and pravoslavie_data["namedays"]:
                final_calendar_data["namedays"] = pravoslavie_data["namedays"]
            if final_calendar_data["fasting"] == "Информация о посте не найдена." and pravoslavie_data["fasting"] != "Информация о посте не найдена.":
                final_calendar_data["fasting"] = pravoslavie_data["fasting"]
            if final_calendar_data["week_info"] == "Информация о седмице не найдена." and pravoslavie_data["week_info"] != "Информация о седмице не найдена.":
                final_calendar_data["week_info"] = pravoslavie_data["week_info"]
            
            print(f"INFO: Данные дополнены из Pravoslavie.ru для {date_str}")

    # Если после всех попыток нет праздников и именин, устанавливаем значения по умолчанию
    if not final_calendar_data["holidays"] and not final_calendar_data["namedays"]:
        final_calendar_data["holidays"] = ["Сегодня больших праздников не найдено."]
        final_calendar_data["namedays"] = ["Сегодня именин не найдено."]

    # image_url всегда None — изображения календаря берём только из assets/images/ (logo.png, daily_quote.png)
    final_calendar_data["image_url"] = None

    cached_calendar_data[date_str] = final_calendar_data
    return final_calendar_data


async def get_calendar_data(date_str: str) -> dict | None:
    """
    Возвращает кэшированные данные календаря для указанной даты.
    Если данные не кэшированы, пытается извлечь их и кэшировать.
    """
    if date_str in cached_calendar_data:
        return cached_calendar_data[date_str]
    
    data = await fetch_and_cache_calendar_data(date_str)
    return data
