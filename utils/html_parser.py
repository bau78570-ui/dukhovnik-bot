import re
import aiohttp
from bs4 import BeautifulSoup

def convert_markdown_to_html(text: str) -> str:
    """
    Преобразует базовый Markdown-текст в HTML.
    Поддерживает:
    - Жирный текст: **текст** -> <b>текст</b>
    - Курсив: _текст_ -> <i>текст</i>
    - Переносы строк: \n (обрабатываются Telegram API в режиме HTML)
    """
    # Жирный текст: **текст** -> <b>текст</b>
    # Используем паттерн с отрицательным опережающим просмотром для корректной обработки
    # любых символов, включая кавычки. Паттерн гарантирует, что между ** нет других **
    text = re.sub(r'\*\*((?:(?!\*\*).)+?)\*\*', r'<b>\1</b>', text, flags=re.DOTALL)
    # Курсив: _текст_ -> <i>текст</i>
    text = re.sub(r'_(.*?)_', r'<i>\1</i>', text)
    # Переносы строк обрабатываются Telegram API в режиме HTML
    return text

async def fetch_html_content(url: str) -> str | None:
    """
    Асинхронно извлекает HTML-содержимое с указанного URL.
    """
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                response.raise_for_status()  # Вызывает исключение для кодов состояния HTTP ошибок
                return await response.text()
        except aiohttp.ClientError as e:
            print(f"Ошибка при получении HTML с {url}: {e}")
            return None
        except Exception as e:
            print(f"Неизвестная ошибка при получении HTML с {url}: {e}")
            return None

def parse_pravoslavie_calendar_page(html_content: str) -> dict:
    """
    Парсит HTML-содержимое страницы православного календаря с pravoslavie.ru
    и извлекает информацию о праздниках, седмицах и мыслях Феофана Затворника.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    calendar_data = {
        "main_holiday": None,
        "holidays": [],
        "week_info": "",
        "theophan_thoughts": [],
        "fasting": "Информация о посте не найдена.",
        "image_url": None,
        "namedays": []
    }

    # Извлечение главного праздника
    # Главный праздник обычно выделен жирным шрифтом и/или иконкой T4.gif/T6.gif
    # Ищем в первом абзаце DD_TEXT
    main_holiday_element = soup.select_one("div.DD_TEXT p.DP_TEXT:first-of-type img[src*='T4.gif'] + b, div.DD_TEXT p.DP_TEXT:first-of-type img[src*='T6.gif'] + b")
    if main_holiday_element:
        calendar_data["main_holiday"] = main_holiday_element.get_text(strip=True)
    else:
        # Если не нашли по иконке, ищем просто жирный текст в первом абзаце
        main_holiday_element = soup.select_one("div.DD_TEXT p.DP_TEXT:first-of-type b")
        if main_holiday_element:
            calendar_data["main_holiday"] = main_holiday_element.get_text(strip=True)

    # Извлечение всех праздников и именин
    all_potential_names = []
    for p_tag in soup.select('div.DD_TEXT p.DP_TEXT'):
        # Извлекаем текст из ссылок на имена святых
        for a_tag in p_tag.select('a[href*="/name/"]'):
            name = a_tag.get_text(strip=True)
            if name and len(name) > 2 and not name.isdigit():
                all_potential_names.append(name)
        # Извлекаем текст из жирных тегов <b>, которые не являются частью ссылок
        for b_tag in p_tag.select('b'):
            if not b_tag.find_parent('a'): # Убедимся, что <b> не внутри <a>
                name = b_tag.get_text(strip=True)
                if name and len(name) > 2 and not name.isdigit():
                    all_potential_names.append(name)

    # Фильтрация и распределение по спискам
    processed_names = set()
    
    # Добавляем главный праздник в список праздников и в обработанные имена
    if calendar_data["main_holiday"]:
        calendar_data["holidays"].append(calendar_data["main_holiday"])
        processed_names.add(calendar_data["main_holiday"])

    for name in all_potential_names:
        if name not in processed_names:
            # Проверяем, является ли имя праздником (по ключевым словам)
            # или если это имя святого, но оно не является именинами
            if "Иконы Божией Матери" in name or "Прп." in name or "Мч." in name or "Свт." in name or "Блж." in name or "Сщмчч." in name:
                calendar_data["holidays"].append(name)
            else:
                calendar_data["namedays"].append(name)
            processed_names.add(name)

    # Удаляем дубликаты из holidays и namedays
    calendar_data["holidays"] = list(dict.fromkeys(calendar_data["holidays"]))
    calendar_data["namedays"] = list(dict.fromkeys(calendar_data["namedays"]))

    # Фильтрация именин, чтобы не дублировать праздники
    final_namedays = []
    for name in calendar_data["namedays"]:
        is_holiday = False
        for holiday in calendar_data["holidays"]:
            if name in holiday or holiday in name: # Проверяем вхождение в обе стороны
                is_holiday = True
                break
        if not is_holiday:
            final_namedays.append(name)
    calendar_data["namedays"] = final_namedays

    # Извлечение информации о Седмице
    week_info_element = soup.find('span', class_='DD_NED')
    if week_info_element:
        calendar_data["week_info"] = week_info_element.get_text(strip=True)
    else:
        # Попробуем найти по тексту в DD_TEXT
        week_text_element = soup.find('div', class_='DD_TEXT', string=lambda text: text and "Седмица" in text)
        if week_text_element:
            calendar_data["week_info"] = week_text_element.strip()

    # Извлечение информации о посте
    fasting_info_element = soup.find('span', class_='DD_TPTXT')
    if fasting_info_element:
        calendar_data["fasting"] = fasting_info_element.get_text(strip=True)
    else:
        # Попробуем найти по тексту в DD_TEXT
        fasting_text_element = soup.find('div', class_='DD_TEXT', string=lambda text: text and ("Поста нет." in text or "Пост" in text))
        if fasting_text_element:
            calendar_data["fasting"] = fasting_text_element.strip()

    # Извлечение основного изображения святого
    main_image_element = soup.select_one('div.DD_ICON img.DI')
    if main_image_element and main_image_element.has_attr('src'):
        image_src = main_image_element['src']
        if not image_src.startswith('http'):
            image_src = "https://days.pravoslavie.ru" + image_src
        calendar_data["image_url"] = image_src

    # Извлечение мыслей Феофана Затворника
    theophan_thoughts_elements = soup.select('div.DD_FEOFAN p.DP_FEOF')
    if theophan_thoughts_elements:
        for thought_elem in theophan_thoughts_elements:
            # Удаляем ссылки на Библию, оставляя только текст
            for a_tag in thought_elem.find_all('a', class_='DA', title='Библия'):
                a_tag.decompose()
            # Используем двойной перенос строки для разделения абзацев
            thought_text = thought_elem.get_text(separator="\n\n", strip=True)
            if thought_text:
                # Разделяем текст на отдельные абзацы
                paragraphs = thought_text.split('\n\n')
                for p in paragraphs:
                    if p.strip():
                        calendar_data["theophan_thoughts"].append(p.strip())
    else:
        calendar_data["theophan_thoughts"].append("Нет мыслей на этот день.")

    return calendar_data

def parse_azbyka_calendar_page(html_content: str) -> dict:
    """
    Парсит HTML-содержимое страницы azbyka.ru и извлекает данные календаря.
    """
    soup = BeautifulSoup(html_content, 'html.parser')

    calendar_data = {
        "main_holiday": None, 
        "holidays": [],
        "fasting": "Поста нет.",
        "namedays": [],
        "week_info": "", 
        "theophan_thoughts": [], 
        "image_url": None, # Добавляем image_url
        "theophan_thoughts": [] 
    }

    # Извлечение праздников
    # Ищем элементы с классом 'days-list-item__title', 'days-list-item__subtitle', 'days-list-item__text'
    # или ссылки внутри 'div.days-list-item__body'
    for elem in soup.select('div.days-list-item__title, div.days-list-item__subtitle, div.days-list-item__text, div.days-list-item__body a'):
        holiday_text = elem.get_text(strip=True)
        if holiday_text and holiday_text not in calendar_data["holidays"]:
            calendar_data["holidays"].append(holiday_text)

    # Извлечение информации о посте
    post_info_element = soup.select_one('div.post-info__text')
    if post_info_element:
        calendar_data["fasting"] = post_info_element.get_text(strip=True)
    else:
        fasting_text_element = soup.find('div', class_='days-list-item__body', string=lambda text: text and "Поста нет." in text)
        if fasting_text_element:
            calendar_data["fasting"] = fasting_text_element.strip()
        else:
            post_status_element = soup.select_one('span.post-status')
            if post_status_element:
                calendar_data["fasting"] = post_status_element.get_text(strip=True)
            else:
                no_fast_text = soup.find(string=lambda text: text and "Поста нет." in text)
                if no_fast_text:
                    calendar_data["fasting"] = no_fast_text.strip()

    # Извлечение именин
    nameday_elements = soup.select('div.days-list-item__body a[href*="/days/svyatie/"]')
    for name_elem in nameday_elements:
        name = name_elem.get_text(strip=True)
        if name and name not in calendar_data["namedays"]:
            calendar_data["namedays"].append(name)
    
    nameday_section = soup.find(lambda tag: tag.name == 'div' and 'Именины:' in tag.get_text(strip=True))
    if nameday_section:
        namedays_str = nameday_section.get_text(strip=True).split("Именины:")[1].strip()
        names = [n.strip() for n in namedays_str.replace(' и ', ',').replace(';', ',').split(',') if n.strip()]
        for name in names:
            if name and name not in calendar_data["namedays"]:
                calendar_data["namedays"].append(name)

    # Фильтрация именин, чтобы не дублировать праздники
    final_namedays = []
    for name in calendar_data["namedays"]:
        is_holiday = False
        if calendar_data["main_holiday"] and name in calendar_data["main_holiday"]:
            is_holiday = True
        for holiday in calendar_data["holidays"]:
            if name in holiday:
                is_holiday = True
                break
        if not is_holiday:
            final_namedays.append(name)
    calendar_data["namedays"] = final_namedays

    # Извлечение изображения, если оно есть
    image_element = soup.select_one('div.days-main-info__image img')
    if image_element and image_element.has_attr('src'):
        image_src = image_element['src']
        if not image_src.startswith('http'):
            image_src = "https://azbyka.ru" + image_src
        calendar_data["image_url"] = image_src

    return calendar_data
