import os
import aiohttp
import logging
import asyncio
import random
import re
from icalendar import Calendar
from datetime import datetime, date, timedelta
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

from aiogram import Bot
from aiogram.types import FSInputFile # Добавляем импорт FSInputFile
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from html import escape

from core.content_library import (
    daily_quotes,
    fasting_content,
    reading_plans,
    daily_words,
    morning_messages,
    evening_prayer_parts,
    evening_reflection_prompts
)
from core.user_database import user_db, get_all_users_with_namedays
from core.content_sender import send_content_message
from core.calendar_data import fetch_and_cache_calendar_data
from core.ai_interaction import get_ai_response # Импортируем для AI-генерации
from core.subscription_checker import is_premium # Импортируем для проверки премиум доступа

MAX_PHOTO_CAPTION_LEN = 1024

def trim_to_limit(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    trimmed = text[:limit].rstrip()
    return trimmed.rsplit(' ', 1)[0] if ' ' in trimmed else trimmed

def trim_to_sentence(text: str, limit: int, min_len: int) -> str:
    if len(text) <= limit:
        return text
    trimmed = text[:limit].rstrip()
    matches = list(re.finditer(r'[.!?…](?:\s|$)', trimmed))
    if matches:
        last_end = matches[-1].end()
        if last_end >= min_len:
            return trimmed[:last_end].rstrip()
    return trim_to_limit(text, limit)

def is_ai_error(text: str | None) -> bool:
    if not text:
        return True
    lowered = text.strip().lower()
    return lowered.startswith("ошибка") or lowered.startswith("произошла ошибка")

def pick_daily_word_image_filename() -> str | None:
    images_dir = os.path.join('assets', 'images', 'daily_word')
    if not os.path.exists(images_dir):
        return None
    image_files = [f for f in os.listdir(images_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    return random.choice(image_files) if image_files else None

def get_morning_fallback_message(target_date: date) -> tuple[str, str]:
    if not morning_messages:
        return (
            "Господи, благослови меня на день грядущий и сохрани в мире сердца.",
            "Сегодня старайся хранить мир и творить добро без лишних слов."
        )
    index = target_date.timetuple().tm_yday % len(morning_messages)
    entry = morning_messages[index]
    return entry["prayer"], entry["exhortation"]

def parse_morning_ai_response(text: str) -> tuple[str, str] | None:
    if not text:
        return None
    prayer_match = re.search(r'(?is)молитва\s*[:\-]\s*(.+?)(?:\n\s*напутствие\s*[:\-]\s*|$)', text)
    exhort_match = re.search(r'(?is)напутствие\s*[:\-]\s*(.+)$', text)
    if prayer_match and exhort_match:
        return prayer_match.group(1).strip(), exhort_match.group(1).strip()
    return None

def sanitize_plain_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r'<[^>]+>', '', text).strip()

def strip_section_label(text: str, label: str) -> str:
    if not text:
        return ""
    pattern = rf'^\s*{re.escape(label)}\s*[:\-]\s*'
    return re.sub(pattern, '', text, flags=re.IGNORECASE).strip()

def build_evening_prayer_by_index(index: int) -> str:
    parts = evening_prayer_parts
    openings = parts.get("openings", [])
    thanksgivings = parts.get("thanksgivings", [])
    repentances = parts.get("repentances", [])
    requests = parts.get("requests", [])
    closings = parts.get("closings", [])

    if not (openings and thanksgivings and repentances and requests and closings):
        return (
            "Господи, благодарю Тебя за этот день. Прости мои согрешения "
            "и даруй мне мирный сон. Аминь."
        )

    sizes = [len(openings), len(thanksgivings), len(repentances), len(requests), len(closings)]
    total = 1
    for size in sizes:
        total *= size
    idx = index % total

    def pick_from(seq, base):
        nonlocal idx
        choice = seq[idx % base]
        idx //= base
        return choice

    opening = pick_from(openings, len(openings))
    thanksgiving = pick_from(thanksgivings, len(thanksgivings))
    repentance = pick_from(repentances, len(repentances))
    request = pick_from(requests, len(requests))
    closing = pick_from(closings, len(closings))
    return " ".join([opening, thanksgiving, repentance, request, closing])

async def get_calendar_theme_from_ical(ical_url: str) -> str | None:
    """
    Скачивает .ics файл, парсит его и возвращает название первого события на текущую дату.
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(ical_url) as response:
                response.raise_for_status()  # Вызовет исключение для статусов 4xx/5xx
                ical_content = await response.text()

        calendar = Calendar.from_ical(ical_content)
        today = date.today()

        for component in calendar.walk():
            if component.name == "VEVENT":
                event_start_dt = component.get('dtstart').dt
                # Если dtstart является datetime, преобразуем его в date
                if isinstance(event_start_dt, datetime):
                    event_start_date = event_start_dt.date()
                else:
                    event_start_date = event_start_dt

                if event_start_date == today:
                    summary = str(component.get('summary'))
                    # Возвращаем только название (первую часть до точки)
                    return summary.split('.')[0].strip()
        return None
    except aiohttp.ClientError as e:
        logging.error(f"Ошибка сети при получении iCal по URL {ical_url}: {e}")
        return None
    except Exception as e:
        logging.error(f"Ошибка при парсинге или обработке iCal: {e}")
        return None

async def get_calendar_theme_from_azbyka(api_key: str | None) -> tuple[str | None, str | None]:
    """
    Получает данные о календарной теме и иконке из API Azbyka.
    """
    if not api_key:
        logging.info("API ключ Azbyka отсутствует. Возвращаем (None, None).")
        return None, None

    url = f"https://azbyka.ru/days/api/day.json?key={api_key}"
    headers = {"Accept": "application/json"}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, ssl=False, headers=headers) as response:
                response.raise_for_status()
                data = await response.json()

                theme = None
                icon_url = None

                # Попытка извлечь главный праздник
                if data.get('main_holiday'):
                    theme = data['main_holiday']['title']
                    icon_url = data['main_holiday'].get('icon_url')
                # Если главного праздника нет, ищем первого святого
                elif data.get('saints') and len(data['saints']) > 0:
                    theme = data['saints'][0]['title']
                    icon_url = data['saints'][0].get('icon_url')
                
                return theme, icon_url

    except aiohttp.ClientError as e:
        logging.error(f"Ошибка сети при получении данных из Azbyka API: {e}")
        return None, None
    except Exception as e:
        logging.error(f"Ошибка при парсинге или обработке данных из Azbyka API: {e}")
        return None, None


async def send_morning_notification(bot: Bot):
    """
    Отправляет утреннее уведомление: сначала приветствие с изображением,
    затем православный календарь в том же формате, что и /calendar.
    """
    logging.info("Начало отправки утренних уведомлений")

    today = datetime.now()
    date_str = today.strftime("%Y%m%d")
    calendar_data = await fetch_and_cache_calendar_data(date_str)

    if not calendar_data:
        logging.error(f"ERROR: calendar_data is unavailable for date {date_str} in morning notification.")
        return

    # Формируем список праздников
    holidays = calendar_data.get("holidays", [])
    if holidays:
        holidays_text = "✨ <b>Праздники:</b>\n" + "\n".join([f"• {h}" for h in holidays]) + "\n\n"
    else:
        holidays_text = "✨ <b>Сегодня больших праздников не найдено.</b>\n\n"

    # Формируем список именин
    namedays = calendar_data.get("namedays", [])
    if namedays:
        namedays_text = "😇 <b>Именины:</b>\n" + "\n".join([f"• {n}" for n in namedays]) + "\n\n"
    else:
        namedays_text = "😇 <b>Именин нет.</b>\n\n"

    # Основная часть сообщения (как в /calendar)
    main_caption_text = (
        f"🗓️ <b>Православный календарь на сегодня</b> ✨\n\n"
        f"🗓️ <b>Дата:</b> {today.strftime('%d.%m.%Y')}\n\n"
        f"{holidays_text}"
        f"ℹ️ <b>Пост:</b> {calendar_data.get('fasting', 'Информация о посте не найдена.')}\n\n"
        f"🏛️ <b>Седмица:</b> {calendar_data.get('week_info', 'Информация о седмице не найдена.')}\n\n"
        f"{namedays_text}"
        f"_Данные предоставлены pravoslavie.ru и azbyka.ru_"
    )

    # Отдельное сообщение для мыслей Феофана Затворника
    theophan_thoughts = calendar_data.get('theophan_thoughts', [])
    if theophan_thoughts:
        header = "📖 <b>Мысли Святителя Феофана Затворника на каждый день года:</b>\n\n"
        formatted_thoughts = []
        for thought in theophan_thoughts:
            cleaned_thought = re.sub(r'^\s*[\(\);,.]+\s*', '', thought)
            if cleaned_thought.strip():
                formatted_thoughts.append(f"✨ <i>{cleaned_thought.strip()}</i>\n\n")
        theophan_message_text = header + "".join(formatted_thoughts).strip()
    else:
        theophan_message_text = None

    # Определяем тему дня для контекста утреннего напутствия
    azbyka_api_key = os.getenv("AZBYKA_API_KEY")
    ical_url = os.getenv("ICAL_URL")
    morning_theme = None
    if azbyka_api_key:
        morning_theme, _ = await get_calendar_theme_from_azbyka(azbyka_api_key)
    if not morning_theme and ical_url:
        morning_theme = await get_calendar_theme_from_ical(ical_url)

    # Генерируем утреннюю молитву и напутствие
    morning_prayer, morning_exhortation = get_morning_fallback_message(today.date())
    morning_prompt = (
        "Составь утреннее приветствие для православного бота.\n"
        "Структура ответа: \n"
        "Молитва: <краткая молитва в каноническом православном стиле, как из молитвослова, 2-4 предложения>\n"
        "Напутствие: <глубокое напутствие на день, 3-5 предложений, связь с Писанием, церковной жизнью или святым>"
        f"{' Учитывай тему дня: ' + morning_theme + '.' if morning_theme else ''}\n"
        "Общий объем 700-900 символов. Без эмодзи, без списков."
    )
    try:
        ai_morning = await get_ai_response(morning_prompt)
        if ai_morning and not is_ai_error(ai_morning):
            parsed = parse_morning_ai_response(ai_morning)
            if parsed:
                morning_prayer, morning_exhortation = parsed
    except Exception as e:
        logging.error(f"Ошибка при генерации утреннего текста через AI: {e}")

    # Приветствие с изображением
    morning_prayer_clean = strip_section_label(sanitize_plain_text(morning_prayer), "молитва")
    morning_exhortation_clean = strip_section_label(sanitize_plain_text(morning_exhortation), "напутствие")
    greeting_prefix = (
        "🌅 <b>Доброе утро!</b>\n\n"
        "🙏 <b>Утренняя молитва:</b>\n"
    )
    greeting_mid = "\n\n💡 <b>Напутствие на день:</b>\n"
    available_len = MAX_PHOTO_CAPTION_LEN - len(greeting_prefix) - len(greeting_mid)
    prayer_limit = max(0, int(available_len * 0.45))
    exhort_limit = max(0, available_len - prayer_limit)
    prayer_text = trim_to_sentence(morning_prayer_clean, prayer_limit, int(prayer_limit * 0.6))
    exhort_text = trim_to_sentence(morning_exhortation_clean, exhort_limit, int(exhort_limit * 0.6))
    greeting_text = (
        f"{greeting_prefix}"
        f"{prayer_text}"
        f"{greeting_mid}"
        f"{exhort_text}"
    )

    morning_image_filename = pick_daily_word_image_filename()
    greeting_image = f"daily_word/{morning_image_filename}" if morning_image_filename else "logo.png"

    # Отправляем уведомления пользователям
    user_ids = list(user_db.keys())
    sent_count = 0
    for user_id in user_ids:
        user_data = user_db[user_id]
        status = user_data.get('status', 'free')

        if status in ['free', 'active']:
            setting_enabled = user_data.get('notifications', {}).get('morning', False)
            if setting_enabled:
                try:
                    await send_content_message(
                        bot=bot,
                        chat_id=user_id,
                        text=greeting_text,
                        image_name=greeting_image
                    )

                    image_url = calendar_data.get("image_url")
                    await send_content_message(
                        bot=bot,
                        chat_id=user_id,
                        text=main_caption_text,
                        image_name=image_url
                    )

                    if theophan_message_text:
                        await send_content_message(
                            bot=bot,
                            chat_id=user_id,
                            text=theophan_message_text
                        )

                    sent_count += 1
                    logging.info(f"Утренние уведомления отправлены пользователю {user_id} (статус: {status})")
                except Exception as e:
                    logging.error(f"Ошибка при отправке утренних уведомлений пользователю {user_id}: {e}")

    logging.info(f"Утренние уведомления отправлены: {sent_count} пользователям")

async def send_afternoon_notification(bot: Bot):
    """
    Отправляет дневное уведомление со Словом дня и AI-размышлением (до 200 символов, с источником).
    """
    logging.info("Начало отправки дневных уведомлений")
    
    # Получаем тему дня (для контекста)
    azbyka_api_key = os.getenv("AZBYKA_API_KEY")
    ical_url = os.getenv("ICAL_URL")
    theme = None
    
    if azbyka_api_key:
        theme, _ = await get_calendar_theme_from_azbyka(azbyka_api_key)
    if not theme and ical_url:
        theme = await get_calendar_theme_from_ical(ical_url)
    
    # Выбираем случайное Слово дня
    scripture = "Неизвестный стих"
    source = "Неизвестный источник"
    base_reflection = "Размышление не найдено."
    
    try:
        if not daily_words:
            logging.error("ERROR: daily_words библиотека пуста для дневной рассылки.")
        else:
            selected_word = random.choice(daily_words)
            scripture = selected_word['scripture']
            source = selected_word.get('source', 'Неизвестный источник')
            base_reflection = selected_word.get('base_reflection', 'Размышление не найдено.')
            logging.info(f"Выбрано Слово Дня для дневной рассылки: {scripture} ({source})")
    except Exception as e:
        logging.error(f"ERROR: Ошибка при выборе слова дня из daily_words для дневной рассылки: {e}")
    
    # Генерируем AI-размышление (почти до лимита Telegram)
    ai_reflection = base_reflection
    try:
        theme_context = f" и темы дня '{theme}'" if theme else ""
        prompt = (
            f"На основе стиха \"{scripture}\"{theme_context} напиши вдохновляющее размышление "
            "в православном стиле: глубоко, тепло, с вниманием к сердцу. "
            "Объем 700-900 символов. 2-3 абзаца, без списков, без эмодзи. "
            "Свяжи мысль со Священным Писанием и простым шагом на сегодня."
        )
        logging.info(f"Сформирован промт для AI в дневной рассылке: {prompt[:100]}...")
        ai_response = await get_ai_response(prompt)
        if ai_response and not is_ai_error(ai_response):
            ai_reflection = ai_response
            logging.info("Получен AI-ответ для дневной рассылки.")
        else:
            logging.warning("WARNING: AI не сгенерировал размышление для дневной рассылки. Используем базовое.")
    except Exception as e:
        logging.error(f"ERROR: Ошибка при генерации AI-размышления в дневной рассылке: {e}. Используем базовое.")
    
    # Формируем сообщение (экранируем все пользовательские данные)
    scripture_escaped = escape(scripture) if scripture else ""
    source_escaped = escape(source) if source else ""
    base_caption = (
        "📖 <b>Слово Дня</b>\n\n"
        f"<i>{scripture_escaped}</i>\n"
        f"<b>Источник:</b> {source_escaped}\n\n"
    )
    hashtags = "#Православие #СловоДня"
    available_len = MAX_PHOTO_CAPTION_LEN - len(base_caption) - len("\n\n") - len(hashtags)
    ai_reflection_escaped = escape(ai_reflection) if ai_reflection else ""
    if ai_reflection_escaped:
        ai_reflection_html = trim_to_sentence(ai_reflection_escaped, max(0, available_len), int(available_len * 0.7))
    else:
        ai_reflection_html = ""
    caption = (
        f"{base_caption}"
        f"{ai_reflection_html}\n\n"
        f"{hashtags}"
    )
    
    # Выбираем случайное изображение
    daily_word_images_path = os.path.join('assets', 'images', 'daily_word')
    fallback_image_path = os.path.join('assets', 'images', 'logo.png')
    image_to_send = fallback_image_path
    try:
        image_filename = pick_daily_word_image_filename()
        if image_filename:
            image_to_send = os.path.join(daily_word_images_path, image_filename)
            logging.info(f"Выбрано изображение для дневной рассылки: {image_to_send}")
        else:
            logging.warning(f"WARNING: В папке {daily_word_images_path} нет подходящих изображений. Используется запасное.")
    except Exception as e:
        logging.error(f"ERROR: Ошибка при выборе изображения для дневной рассылки: {e}. Используется запасное.")
    
    # Отправляем уведомления
    user_ids = list(user_db.keys())
    sent_count = 0
    for user_id in user_ids:
        user_data = user_db[user_id]
        status = user_data.get('status', 'free')
        
        if status in ['free', 'active']:
            setting_enabled = user_data.get('notifications', {}).get('daily', False)
            if setting_enabled:
                try:
                    photo_file = FSInputFile(image_to_send)
                    await bot.send_photo(user_id, photo=photo_file, caption=caption, parse_mode=ParseMode.HTML)
                    sent_count += 1
                    logging.info(f"Дневное уведомление отправлено пользователю {user_id} (статус: {status})")
                except Exception as e:
                    logging.error(f"ERROR: Ошибка при отправке дневного уведомления пользователю {user_id}: {e}")
    
    logging.info(f"Дневные уведомления отправлены: {sent_count} пользователям")

async def send_evening_notification(bot: Bot):
    """
    Отправляет вечернее уведомление с вечерней молитвой и вопросом для рефлексии.
    Формат: "Добрый вечер! Вечерняя молитва: [молитва]. Что сегодня принесло радость?"
    """
    logging.info("Начало отправки вечерних уведомлений")
    
    # Выбираем библейский текст
    scripture = "Неизвестный стих"
    source = "Неизвестный источник"
    if daily_words:
        selected_word = random.choice(daily_words)
        scripture = selected_word.get("scripture", scripture)
        source = selected_word.get("source", source)

    # Составляем молитву из частей (более 100 вариантов)
    day_index = datetime.now().timetuple().tm_yday
    evening_prayer = build_evening_prayer_by_index(day_index)
    
    # Формируем финальное сообщение (экранируем пользовательские данные)
    scripture_escaped = escape(scripture) if scripture else ""
    source_escaped = escape(source) if source else ""
    evening_prayer_escaped = escape(evening_prayer) if evening_prayer else ""

    reflection_prompt = "Поделитесь в чате тем, что сегодня особенно откликнулось в сердце."
    if evening_reflection_prompts:
        prompt_index = day_index % len(evening_reflection_prompts)
        reflection_prompt = evening_reflection_prompts[prompt_index]
    reflection_prompt_escaped = escape(reflection_prompt)

    base_prefix = (
        "🌙 <b>Добрый вечер!</b>\n\n"
        "📖 <b>Слово на вечер:</b>\n"
        f"<i>{scripture_escaped}</i>\n"
        f"<b>Источник:</b> {source_escaped}\n\n"
        "🙏 <b>Вечерняя молитва:</b>\n"
    )
    reflection_header = "\n\n💬 <b>Поговорим?</b>\n"
    remaining_len = MAX_PHOTO_CAPTION_LEN - len(base_prefix) - len(reflection_header)
    prayer_limit = max(0, int(remaining_len * 0.65))
    reflection_limit = max(0, remaining_len - prayer_limit)
    evening_prayer_trimmed = trim_to_sentence(evening_prayer_escaped, prayer_limit, int(prayer_limit * 0.6))
    reflection_trimmed = trim_to_sentence(reflection_prompt_escaped, reflection_limit, int(reflection_limit * 0.6))

    caption = f"{base_prefix}{evening_prayer_trimmed}{reflection_header}{reflection_trimmed}"
    
    # Выбираем случайное изображение (используем те же изображения, что и для дневного уведомления)
    daily_word_images_path = os.path.join('assets', 'images', 'daily_word')
    fallback_image_path = os.path.join('assets', 'images', 'logo.png')
    image_to_send = fallback_image_path
    try:
        image_filename = pick_daily_word_image_filename()
        if image_filename:
            image_to_send = os.path.join(daily_word_images_path, image_filename)
            logging.info(f"Выбрано изображение для вечерней рассылки: {image_to_send}")
        else:
            logging.warning(f"WARNING: В папке {daily_word_images_path} нет подходящих изображений. Используется запасное.")
    except Exception as e:
        logging.error(f"ERROR: Ошибка при выборе изображения для вечерней рассылки: {e}. Используется запасное.")
    
    # Отправляем уведомления пользователям
    user_ids = list(user_db.keys())
    sent_count = 0
    for user_id in user_ids:
        user_data = user_db[user_id]
        status = user_data.get('status', 'free')
        
        if status in ['free', 'active']:
            setting_enabled = user_data.get('notifications', {}).get('evening', False)
            if setting_enabled:
                try:
                    photo_file = FSInputFile(image_to_send)
                    await bot.send_photo(user_id, photo=photo_file, caption=caption, parse_mode=ParseMode.HTML)
                    sent_count += 1
                    logging.info(f"Вечернее уведомление отправлено пользователю {user_id} (статус: {status})")
                except Exception as e:
                    logging.error(f"Ошибка при отправке вечернего уведомления пользователю {user_id}: {e}")
    
    logging.info(f"Вечерние уведомления отправлены: {sent_count} пользователям")

scheduler = AsyncIOScheduler(timezone="Europe/Moscow")

async def check_namedays(bot: Bot):
    """
    Проверяет именины на завтрашний день и отправляет уведомления пользователям.
    """
    logging.info("Запуск проверки именин...")
    
    tomorrow = datetime.now() + timedelta(days=1)
    calendar_data = await fetch_and_cache_calendar_data(tomorrow.strftime("%Y%m%d"))

    if not calendar_data:
        logging.error("ERROR: calendar_data is unavailable for nameday check.")
        return
    
    tomorrow_date = tomorrow.strftime('%d %B')

    saints_on_nameday = set()
    if calendar_data.get("namedays"):
        for saint_name in calendar_data["namedays"]:
            if saint_name == "Сегодня именин не найдено.":
                continue
            saints_on_nameday.add(saint_name.split(' ')[0].lower())

    users_with_namedays = get_all_users_with_namedays()

    for user_id, persons in users_with_namedays.items():
        for person_name in persons:
            if person_name.lower() in saints_on_nameday:
                notification_text = (
                    f"✨ Напоминание! Завтра, {tomorrow_date}, день Ангела у вашего близкого '{person_name}'. "
                    "Не забудьте поздравить!"
                )
                try:
                    await bot.send_message(user_id, notification_text, parse_mode=ParseMode.HTML)
                    logging.info(f"Отправлено уведомление об именинах пользователю {user_id} для {person_name}")
                except Exception as e:
                    logging.error(f"Не удалось отправить уведомление об именинах пользователю {user_id}: {e}")
    logging.info("Проверка именин завершена.")
