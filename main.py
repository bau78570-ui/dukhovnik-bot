import asyncio
import logging
import os
import sys # Добавляем импорт sys

# Проверяем, активно ли виртуальное окружение
if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
    logging.warning("Виртуальное окружение не активно. Пожалуйста, убедитесь, что вы запускаете скрипт в активированном .venv.")

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from aiogram.fsm.storage.memory import MemoryStorage # Импортируем MemoryStorage
from dotenv import load_dotenv

from handlers import start, text_handler, premium_content, free_content, callbacks, settings, nameday, dukhovnik_handler, favorites, support_handler, legal_handler
from handlers.admin_handler import router as admin_router
from core.scheduler import scheduler, send_morning_notification, send_afternoon_notification, send_evening_notification # check_namedays
from core.subscription_checker import check_access # Импортируем мидлварь проверки доступа
from core.user_database import user_db, get_user # Импортируем user_db и get_user
# from core.calendar_data import cached_calendar_data # Импортируем кэш календаря

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()  # Также выводим в консоль
    ]
)

# Загрузка переменных окружения из файла .env
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Создание объектов Bot и Dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage()) # Инициализируем Dispatcher с MemoryStorage

# Асинхронная функция для установки главного меню
async def set_main_menu(bot: Bot):
    """
    Создает и устанавливает основное меню команд для бота.
    """
    print("INFO: Setting main menu commands...")
    main_menu_commands = [
        BotCommand(command="/start", description="🔄 Перезапустить бота"),
        BotCommand(command="/dukhovnik", description="💬 Поговорить с Духовником"),
        BotCommand(command="/calendar", description="🗓️ Православный календарь"),
        BotCommand(command="/molitva", description="🙏 Молитва"),
        BotCommand(command="/daily_word", description="📖 Слово дня (Premium)"),
        BotCommand(command="/favorites", description="⭐️ Избранное"), # Добавляем команду для избранного
        BotCommand(command="/subscribe", description="🌟 Оформить Premium"),
        BotCommand(command="/settings", description="⚙️ Настройки"),
        BotCommand(command="/support", description="💬 Поддержка / Обратная связь"),
        BotCommand(command="/documents", description="📑 Документы")
    ]
    await bot.set_my_commands(main_menu_commands)
    print("INFO: Main menu commands set successfully.")

# Асинхронная функция для запуска бота
async def main() -> None:
    """
    Основная функция для запуска long polling.
    """
    # Удаляем старые задачи, если они есть, чтобы избежать дублирования при перезапуске
    if scheduler.get_job('morning_notification_job'):
        scheduler.remove_job('morning_notification_job')
    if scheduler.get_job('afternoon_notification_job'):
        scheduler.remove_job('afternoon_notification_job')
    if scheduler.get_job('evening_notification_job'):
        scheduler.remove_job('evening_notification_job')

    # Добавляем задачи в планировщик с явными ID
    scheduler.add_job(send_morning_notification, trigger='cron', hour=8, minute=0, args=[bot], timezone='Europe/Moscow', id='morning_notification_job')
    scheduler.add_job(send_afternoon_notification, trigger='cron', hour=14, minute=0, args=[bot], timezone='Europe/Moscow', id='afternoon_notification_job')
    scheduler.add_job(send_evening_notification, trigger='cron', hour=20, minute=0, args=[bot], timezone='Europe/Moscow', id='evening_notification_job')
    # scheduler.add_job(check_namedays, trigger='cron', hour=7, minute=0, args=(bot,)) # Запускаем проверку именин в 7 утра

    # Логируем информацию о запланированных задачах (без next_run_time, чтобы избежать ошибки)
    logging.info(f"Job 'morning_notification_job' added for 08:00 MSK.")
    logging.info(f"Job 'afternoon_notification_job' added for 14:00 MSK.")
    logging.info(f"Job 'evening_notification_job' added for 20:00 MSK.")

    # Запускаем планировщик, если он еще не запущен
    if not scheduler.running:
        scheduler.start()

    # Применяем мидлварь проверки доступа ко всем сообщениям и колбэкам
    dp.message.middleware(check_access)
    dp.callback_query.middleware(check_access)

    # Подключаем роутеры из handlers
    dp.include_router(start.router)
    dp.include_router(settings.router)
    dp.include_router(admin_router) # Подключаем роутер для админ-панели
    dp.include_router(premium_content.router) # Оставляем для /daily_word и /molitva
    dp.include_router(free_content.router) # Раскомментировано для /menu и других бесплатных команд
    dp.include_router(dukhovnik_handler.router) # Подключаем новый роутер для /dukhovnik
    dp.include_router(favorites.router) # Подключаем роутер для избранного
    # dp.include_router(nameday.router) # Закомментировано: именины
    dp.include_router(callbacks.router) # Оставляем для общих колбэков, но закомментируем связанные с постом
    dp.include_router(support_handler.router) # Подключаем роутер для поддержки
    dp.include_router(legal_handler.router) # Подключаем роутер для юридических документов
    dp.include_router(text_handler.router) # Этот роутер должен быть последним
    from handlers.admin import router as admin_router
dp.include_router(admin_router)

    # Устанавливаем главное меню
    await set_main_menu(bot)
    
    await dp.start_polling(bot)

# Точка входа
if __name__ == "__main__":
    asyncio.run(main())
