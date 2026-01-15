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

from core.content_library import daily_quotes, fasting_content, reading_plans, daily_words # Добавляем daily_words
from core.user_database import user_db, get_all_users_with_namedays
from core.content_sender import send_content_message
from core.calendar_data import fetch_and_cache_calendar_data
from core.ai_interaction import get_ai_response # Импортируем для AI-генерации
from core.subscription_checker import is_premium # Импортируем для проверки премиум доступа
from utils.html_parser import convert_markdown_to_html # Импортируем для преобразования markdown в HTML

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
        theophan_message_text = (
            "📖 <b>Мысли Святителя Феофана Затворника на каждый день года:</b>\n"
            "Нет мыслей на этот день."
        )

    # Приветствие с изображением
    greeting_text = (
        "🌅 <b>Доброе утро!</b>\n\n"
        "Помолимся на день грядущий. Пусть он будет благословенным."
    )
    greeting_image = "logo.png"

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
    
    # Генерируем AI-размышление (до 200 символов)
    ai_reflection = base_reflection
    try:
        theme_context = f" и темы дня '{theme}'" if theme else ""
        prompt = (
            f"На основе стиха _{scripture}_{theme_context}, "
            "напиши очень краткое (до 200 символов) вдохновляющее размышление в позитивном стиле "
            "(Норман Пил, православный контекст). Сделай акцент на практическом применении "
            "этой мысли в сегодняшнем дне."
        )
        logging.info(f"Сформирован промт для AI в дневной рассылке: {prompt[:100]}...")
        ai_response = await get_ai_response(prompt)
        if ai_response:
            # Ограничиваем до 200 символов
            ai_reflection = ai_response[:200].rsplit(' ', 1)[0] if len(ai_response) > 200 else ai_response
            logging.info("Получен AI-ответ для дневной рассылки.")
        else:
            logging.warning("WARNING: AI не сгенерировал размышление для дневной рассылки. Используем базовое.")
    except Exception as e:
        logging.error(f"ERROR: Ошибка при генерации AI-размышления в дневной рассылке: {e}. Используем базовое.")
    
    # Преобразуем markdown в HTML
    ai_reflection_html = convert_markdown_to_html(ai_reflection)
    
    # Формируем сообщение (экранируем все пользовательские данные)
    scripture_escaped = escape(scripture) if scripture else ""
    source_escaped = escape(source) if source else ""
    caption = (
        f"📖 <b>Слово Дня</b>\n\n"
        f"<i>{scripture_escaped}</i>\n"
        f"<b>Источник:</b> {source_escaped}\n\n"
        f"{ai_reflection_html}\n\n"
        f"#Православие #СловоДня"
    )
    
    # Выбираем случайное изображение
    daily_word_images_path = 'assets/images/daily_word/'
    fallback_image_path = 'assets/images/logo.png'
    image_to_send = fallback_image_path
    try:
        if os.path.exists(daily_word_images_path) and os.listdir(daily_word_images_path):
            image_files = [f for f in os.listdir(daily_word_images_path) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
            if image_files:
                random_image = random.choice(image_files)
                image_to_send = os.path.join(daily_word_images_path, random_image)
                logging.info(f"Выбрано изображение для дневной рассылки: {image_to_send}")
            else:
                logging.warning(f"WARNING: В папке {daily_word_images_path} нет подходящих изображений. Используется запасное.")
        else:
            logging.warning(f"WARNING: Папка {daily_word_images_path} не найдена или пуста. Используется запасное изображение.")
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
    
    # Генерируем вечернюю молитву через AI (100-150 символов)
    evening_prayer_prompt = (
        "Напиши очень краткую (1 абзац, 100-150 символов) вечернюю молитву в позитивном стиле "
        "Нормана Пила с православным контекстом. Молитва должна быть спокойной, благодарственной, "
        "на покой и рефлексию. Используй современный русский язык, без архаики. "
        "Акцент на благодарности за день и просьбе о покое на ночь."
    )
    
    evening_prayer = "Господи, благодарю Тебя за этот день. Дай мне покой и мир на ночь."
    try:
        ai_prayer = await get_ai_response(evening_prayer_prompt)
        if ai_prayer:
            # Ограничиваем молитву до 150 символов
            evening_prayer = ai_prayer[:150].rsplit(' ', 1)[0] if len(ai_prayer) > 150 else ai_prayer
            logging.info("Вечерняя молитва сгенерирована через AI")
        else:
            logging.warning("AI не сгенерировал вечернюю молитву, используется запасная")
    except Exception as e:
        logging.error(f"Ошибка при генерации вечерней молитвы через AI: {e}")
    
    # Формируем финальное сообщение (экранируем пользовательские данные)
    evening_prayer_escaped = escape(evening_prayer) if evening_prayer else ""
    caption = (
        f"🌙 <b>Добрый вечер!</b>\n\n"
        f"🙏 <b>Вечерняя молитва:</b>\n{evening_prayer_escaped}\n\n"
        f"💭 <b>Что сегодня принесло радость?</b> Поделитесь в чате!"
    )
    
    # Выбираем случайное изображение (используем те же изображения, что и для дневного уведомления)
    daily_word_images_path = 'assets/images/daily_word/'
    fallback_image_path = 'assets/images/logo.png'
    image_to_send = fallback_image_path
    try:
        if os.path.exists(daily_word_images_path) and os.listdir(daily_word_images_path):
            image_files = [f for f in os.listdir(daily_word_images_path) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
            if image_files:
                random_image = random.choice(image_files)
                image_to_send = os.path.join(daily_word_images_path, random_image)
                logging.info(f"Выбрано изображение для вечерней рассылки: {image_to_send}")
            else:
                logging.warning(f"WARNING: В папке {daily_word_images_path} нет подходящих изображений. Используется запасное.")
        else:
            logging.warning(f"WARNING: Папка {daily_word_images_path} не найдена или пуста. Используется запасное изображение.")
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
    if calendar_data.get("saints"):
        for saint_name in calendar_data["saints"]:
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
