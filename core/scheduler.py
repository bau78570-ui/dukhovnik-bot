import os
import aiohttp
import logging
import asyncio
import random
from icalendar import Calendar
from datetime import datetime, date, timedelta
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

from aiogram import Bot
from aiogram.types import FSInputFile # Добавляем импорт FSInputFile
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from core.content_library import daily_quotes, fasting_content, reading_plans, daily_words # Добавляем daily_words
from core.user_database import user_db, get_all_users_with_namedays
from core.content_sender import send_content_message
from core.calendar_data import fetch_and_cache_calendar_data
from core.ai_interaction import get_ai_response # Импортируем для AI-генерации
from core.subscription_checker import is_premium # Импортируем для проверки премиум доступа

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
    Отправляет утреннее уведомление с гибридной логикой получения темы дня.
    """
    azbyka_api_key = os.getenv("AZBYKA_API_KEY")
    ical_url = os.getenv("ICAL_URL")
    admin_id = os.getenv("ADMIN_ID")

    theme = None
    icon_url = None

    # Попытка получить тему из Azbyka API (План А)
    if azbyka_api_key:
        theme, icon_url = await get_calendar_theme_from_azbyka(azbyka_api_key)
        if theme:
            logging.info(f"Тема дня получена из Azbyka API: {theme}")
        else:
            logging.warning("Не удалось получить тему дня из Azbyka API. Переключаемся на iCal.")

    # Если тема не получена из Azbyka, пытаемся получить из iCal (План Б)
    if not theme and ical_url:
        theme = await get_calendar_theme_from_ical(ical_url)
        if theme:
            logging.info(f"Тема дня получена из iCal: {theme}")
        else:
            logging.error("Не удалось получить тему дня ни из Azbyka API, ни из iCal. Уведомление не будет отправлено.")
            return

    if not theme:
        logging.error("Тема дня не определена. Уведомление не будет отправлено.")
        return

    # Выбор стиха и базовой мысли
    scripture = "Неизвестный стих"
    base_reflection = "Размышление не найдено."
    try:
        if not daily_words:
            logging.error("ERROR: daily_words библиотека пуста в send_morning_notification.")
            # Можно отправить заглушку или пропустить
        else:
            selected_word = random.choice(daily_words)
            scripture = selected_word['scripture']
            base_reflection = selected_word['base_reflection']
            logging.info(f"Выбрано Слово Дня для утренней рассылки: {scripture}")
    except Exception as e:
        logging.error(f"ERROR: Ошибка при выборе слова дня из daily_words в send_morning_notification: {e}")

    # Генерация AI-текста
    ai_reflection = base_reflection
    try:
        prompt = (
            f"На основе стиха _{scripture}_ и темы дня '{theme}', "
            "напиши очень краткое (1 абзац, до 100 символов) вдохновляющее размышление в позитивном стиле "
            "(Норман Пил, православный контекст). Сделай акцент на практическом применении "
            "этой мысли в сегодняшнем дне."
        )
        logging.info(f"Сформирован промт для AI в send_morning_notification: {prompt[:100]}...")
        ai_response = await get_ai_response(prompt)
        if ai_response:
            ai_reflection = ai_response
            logging.info("Получен AI-ответ для утренней рассылки.")
        else:
            logging.warning("WARNING: AI не сгенерировал размышление для утренней рассылки. Используем базовое.")
    except Exception as e:
        logging.error(f"ERROR: Ошибка при генерации AI-размышления в send_morning_notification: {e}. Используем базовое.")

    # Формирование caption
    today_formatted = datetime.now().strftime('%d.%m.%Y')
    
    # Обрезаем scripture, если он слишком длинный
    max_scripture_len = 200
    display_scripture = scripture
    if len(scripture) > max_scripture_len:
        display_scripture = scripture[:max_scripture_len].rsplit(' ', 1)[0] + "..." # Обрезаем по слову
    
    caption = (
        f"✨ <b>{today_formatted} - {theme}</b> ✨\n\n"
        f"📖 <b>{display_scripture}</b>\n\n"
        f"{ai_reflection}\n\n"
        f"#Православие #СловоДня #Размышление"
    )

    # Выбираем случайное изображение из assets/images/daily_word/ для рассылки
    image_dir = 'assets/images/daily_word/'
    image_name = 'bible_study.png' # Запасное изображение
    try:
        if os.path.exists(image_dir):
            image_files = [f for f in os.listdir(image_dir) if f.endswith(('.png', '.jpg', '.jpeg'))]
            if image_files:
                image_name = random.choice(image_files)
                logging.info(f"Выбрано изображение для утренней рассылки: {image_name}")
            else:
                logging.warning(f"WARNING: В папке {image_dir} нет подходящих изображений для утренней рассылки. Используется запасное.")
        else:
            logging.warning(f"WARNING: Папка {image_dir} не существует для утренней рассылки. Используется запасное изображение.")
    except Exception as e:
        logging.error(f"ERROR: Ошибка при выборе изображения для утренней рассылки: {e}. Используется запасное.")


    # Рассылка уведомлений
    for user_id, user_data in user_db.items():
        logging.info(f"\n--- Processing User {user_id} ---")

        logging.info(f"Checking morning notification setting for user {user_id}...")
        setting_enabled = user_data.get('notifications', {}).get('morning', False)
        logging.info(f"Morning notification enabled: {setting_enabled}")
        if setting_enabled:
            logging.info(f"Checking access for user {user_id}...")
            admin_id_str = os.getenv("ADMIN_ID")
            logging.info(f"User ID: {user_id}, Admin ID from .env: {admin_id_str}")
            has_access = await is_premium(user_id) or (str(user_id) == admin_id_str)
            logging.info(f"User has access: {has_access}")
            if has_access:
                logging.info(f"Attempting to send notification to user {user_id}...")
                try:
                    daily_word_images_path = 'assets/images/daily_word/'
                    fallback_image_path = 'assets/images/logo.png'
                    image_to_send = fallback_image_path

                    if os.path.exists(daily_word_images_path) and os.listdir(daily_word_images_path):
                        image_files = [f for f in os.listdir(daily_word_images_path) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
                        if image_files:
                            random_image = random.choice(image_files)
                            image_to_send = os.path.join(daily_word_images_path, random_image)
                        else:
                            logging.warning(f"Папка {daily_word_images_path} не содержит изображений.")
                    else:
                        os.makedirs(daily_word_images_path, exist_ok=True)
                        logging.warning(f"Папка {daily_word_images_path} не найдена или пуста. Используется {fallback_image_path}.")
                    
                    photo_file = FSInputFile(image_to_send)
                    await bot.send_photo(user_id, photo=photo_file, caption=caption, parse_mode='HTML')

                    logging.info(f"Notification sent successfully to user {user_id}.")
                except Exception as e:
                    logging.error(f"ERROR sending notification to user {user_id}: {e}")
            else:
                logging.info(f"User {user_id} does not have access to morning notifications (not Premium/Admin).")
        else:
            logging.info(f"Morning notifications are disabled for user {user_id}.")

async def _send_daily_word_notification(bot: Bot, notification_type: str, hour: int, minute: int):
    """
    Вспомогательная функция для отправки ежедневных уведомлений (утро, день, вечер).
    """
    azbyka_api_key = os.getenv("AZBYKA_API_KEY")
    ical_url = os.getenv("ICAL_URL")
    admin_id_str = os.getenv("ADMIN_ID")

    theme = None
    icon_url = None

    # Попытка получить тему из Azbyka API (План А)
    if azbyka_api_key:
        theme, icon_url = await get_calendar_theme_from_azbyka(azbyka_api_key)
        if theme:
            logging.info(f"Тема дня получена из Azbyka API: {theme}")
        else:
            logging.warning("Не удалось получить тему дня из Azbyka API. Переключаемся на iCal.")

    # Если тема не получена из Azbyka, пытаемся получить из iCal (План Б)
    if not theme and ical_url:
        theme = await get_calendar_theme_from_ical(ical_url)
        if theme:
            logging.info(f"Тема дня получена из iCal: {theme}")
        else:
            logging.error("Не удалось получить тему дня ни из Azbyka API, ни из iCal. Уведомление не будет отправлено.")
            return

    if not theme:
        logging.error("Тема дня не определена. Уведомление не будет отправлено.")
        return

    # Выбор стиха и базовой мысли
    scripture = "Неизвестный стих"
    base_reflection = "Размышление не найдено."
    try:
        if not daily_words:
            logging.error(f"ERROR: daily_words библиотека пуста для {notification_type} рассылки.")
        else:
            selected_word = random.choice(daily_words)
            scripture = selected_word['scripture']
            base_reflection = selected_word['base_reflection']
            logging.info(f"Выбрано Слово Дня для {notification_type} рассылки: {scripture}")
    except Exception as e:
        logging.error(f"ERROR: Ошибка при выборе слова дня из daily_words для {notification_type} рассылки: {e}")

    # Генерация AI-текста
    ai_reflection = base_reflection
    try:
        prompt = (
            f"На основе стиха _{scripture}_ и темы дня '{theme}', "
            "напиши очень краткое (1-2 абзаца, до 300 символов) вдохновляющее размышление в позитивном стиле "
            "(Норман Пил, православный контекст). Сделай акцент на практическом применении "
            "этой мысли в сегодняшнем дне."
        )
        logging.info(f"Сформирован промт для AI в {notification_type} рассылке: {prompt[:100]}...")
        ai_response = await get_ai_response(prompt)
        if ai_response:
            ai_reflection = ai_response
            logging.info(f"Получен AI-ответ для {notification_type} рассылки.")
        else:
            logging.warning(f"WARNING: AI не сгенерировал размышление для {notification_type} рассылки. Используем базовое.")
    except Exception as e:
        logging.error(f"ERROR: Ошибка при генерации AI-размышления в {notification_type} рассылке: {e}. Используем базовое.")

    # Формирование caption
    today_formatted = datetime.now().strftime('%d.%m.%Y')
    caption = (
        f"✨ <b>{today_formatted} - {theme}</b> ✨\n\n"
        f"📖 <b>{scripture}</b>\n\n"
        f"{ai_reflection}\n\n"
        f"#Православие #СловоДня #Размышление"
    )

    # Выбираем случайное изображение из assets/images/daily_word/ для рассылки
    daily_word_images_path = 'assets/images/daily_word/'
    fallback_image_path = 'assets/images/logo.png'
    image_to_send = fallback_image_path
    try:
        if os.path.exists(daily_word_images_path) and os.listdir(daily_word_images_path):
            image_files = [f for f in os.listdir(daily_word_images_path) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
            if image_files:
                random_image = random.choice(image_files)
                image_to_send = os.path.join(daily_word_images_path, random_image)
                logging.info(f"Выбрано изображение для {notification_type} рассылки: {image_to_send}")
            else:
                logging.warning(f"WARNING: В папке {daily_word_images_path} нет подходящих изображений для {notification_type} рассылки. Используется запасное.")
        else:
            os.makedirs(daily_word_images_path, exist_ok=True)
            logging.warning(f"WARNING: Папка {daily_word_images_path} не найдена или пуста для {notification_type} рассылки. Используется запасное изображение.")
    except Exception as e:
        logging.error(f"ERROR: Ошибка при выборе изображения для {notification_type} рассылки: {e}. Используется запасное.")

    # Рассылка уведомлений
    for user_id, user_data in user_db.items():
        logging.info(f"\n--- Processing User {user_id} for {notification_type} notification ---")

        logging.info(f"Checking {notification_type} notification setting for user {user_id}...")
        setting_enabled = user_data.get('notifications', {}).get(notification_type, False)
        logging.info(f"{notification_type} notification enabled: {setting_enabled}")
        if setting_enabled:
            logging.info(f"Checking access for user {user_id}...")
            has_access = await is_premium(user_id) or (str(user_id) == admin_id_str)
            logging.info(f"User has access: {has_access}")
            if has_access:
                logging.info(f"Attempting to send {notification_type} notification to user {user_id}...")
                try:
                    photo_file = FSInputFile(image_to_send)
                    await bot.send_photo(user_id, photo=photo_file, caption=caption, parse_mode='HTML')
                    logging.info(f"{notification_type} notification sent successfully to user {user_id}.")
                except Exception as e:
                    logging.error(f"ERROR sending {notification_type} notification to user {user_id}: {e}")
            else:
                logging.info(f"User {user_id} does not have access to {notification_type} notifications (not Premium/Admin).")
        else:
            logging.info(f"{notification_type} notifications are disabled for user {user_id}.")

async def send_morning_notification(bot: Bot):
    """
    Отправляет утреннее уведомление с гибридной логикой получения темы дня.
    """
    await _send_daily_word_notification(bot, 'morning', 8, 0)

async def send_afternoon_notification(bot: Bot):
    """
    Отправляет дневное уведомление с гибридной логикой получения темы дня.
    """
    await _send_daily_word_notification(bot, 'afternoon', 14, 0)

async def send_evening_notification(bot: Bot):
    """
    Отправляет вечернее уведомление с гибридной логикой получения темы дня.
    """
    await _send_daily_word_notification(bot, 'evening', 20, 0)

scheduler = AsyncIOScheduler(timezone="Europe/Moscow")

async def check_namedays(bot: Bot):
    """
    Проверяет именины на завтрашний день и отправляет уведомления пользователям.
    """
    logging.info("Запуск проверки именин...")
    
    tomorrow = datetime.now() + timedelta(days=1)
    calendar_data = await fetch_and_cache_calendar_data(tomorrow.strftime("%Y%m%d"))
    
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
                    await bot.send_message(user_id, notification_text, parse_mode='HTML')
                    logging.info(f"Отправлено уведомление об именинах пользователю {user_id} для {person_name}")
                except Exception as e:
                    logging.error(f"Не удалось отправить уведомление об именинах пользователю {user_id}: {e}")
    logging.info("Проверка именин завершена.")
