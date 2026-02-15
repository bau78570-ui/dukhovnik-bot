import asyncio
import logging
import os
import sys # Добавляем импорт sys
from datetime import datetime

# Проверяем, активно ли виртуальное окружение
if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
    logging.warning("Виртуальное окружение не активно. Пожалуйста, убедитесь, что вы запускаете скрипт в активированном .venv.")

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from aiogram.types.bot_command_scope_chat import BotCommandScopeChat
from aiogram.fsm.storage.memory import MemoryStorage # Импортируем MemoryStorage
from dotenv import load_dotenv

from handlers import start, text_handler, premium_content, free_content, callbacks, settings, nameday, favorites, support_handler, legal_handler
from handlers.admin_handler import router as admin_router
from handlers.subscription import router as subscription_router
from core.scheduler import scheduler, send_morning_notification, send_afternoon_notification, send_evening_notification, send_subscription_reminder, send_free_period_ending_notification # check_namedays
from core.subscription_checker import check_access # Импортируем мидлварь проверки доступа
from core.user_database import user_db, get_user # Импортируем user_db и get_user
from core.calendar_data import clear_calendar_cache

# Настройка логирования с ротацией файлов
from logging.handlers import RotatingFileHandler

# Создаем handler с ротацией (максимум 10 МБ, 5 резервных копий)
rotating_handler = RotatingFileHandler(
    'bot.log',
    maxBytes=10*1024*1024,  # 10 МБ
    backupCount=5,
    encoding='utf-8'
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        rotating_handler,
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
        BotCommand(command="/new_chat", description="✨ Начать новую беседу с Духовником"),
        BotCommand(command="/calendar", description="🗓️ Православный календарь"),
        BotCommand(command="/molitva", description="🙏 Молитва"),
        # BotCommand(command="/daily_word", description="📖 Слово дня (Premium)"), # Скрыто - доступно только через уведомления
        BotCommand(command="/favorites", description="⭐️ Избранное"), # Добавляем команду для избранного
        BotCommand(command="/subscribe", description="🌟 Оформить Premium"),
        BotCommand(command="/settings", description="⚙️ Настройки"),
        BotCommand(command="/support", description="💬 Поддержка / Обратная связь"),
        BotCommand(command="/documents", description="📑 Документы")
    ]
    await bot.set_my_commands(main_menu_commands)

    admin_id_raw = os.getenv("ADMIN_ID")
    try:
        admin_id = int(admin_id_raw) if admin_id_raw else None
    except ValueError:
        admin_id = None
    if admin_id:
        admin_menu_commands = main_menu_commands + [
            BotCommand(command="/admin", description="🛠️ Admin панель"),
            BotCommand(command="/stats", description="📊 Аналитика трафика"),
            BotCommand(command="/admin_stats", description="📈 Статистика подписок"),
            BotCommand(command="/admin_check_subscription", description="🔎 Статус подписки"),
            BotCommand(command="/admin_activate_premium", description="⭐ Активировать Premium"),
            BotCommand(command="/support_history", description="🧾 История поддержки"),
            BotCommand(command="/support_status", description="🏷️ Статус тикета"),
            BotCommand(command="/support_reply", description="✉️ Ответить пользователю")
        ]
        await bot.set_my_commands(admin_menu_commands, scope=BotCommandScopeChat(chat_id=admin_id))
    print("INFO: Main menu commands set successfully.")

# Асинхронная функция для запуска бота
async def main() -> None:
    """
    Основная функция для запуска long polling.
    """
    import traceback
    clear_calendar_cache()  # Сброс кэша при старте (убирает старые данные с image_url с сайтов)

    logging.info("="*80)
    logging.info("🚀 ЗАПУСК ФУНКЦИИ main() - НАЧАЛО ИНИЦИАЛИЗАЦИИ БОТА")
    logging.info(f"Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logging.info(f"Call stack:\n{''.join(traceback.format_stack())}")
    logging.info("="*80)
    
    # Выводим все текущие задачи в планировщике
    existing_jobs = scheduler.get_jobs()
    logging.info(f"📋 Текущих задач в планировщике: {len(existing_jobs)}")
    for job in existing_jobs:
        try:
            next_run = getattr(job, 'next_run_time', 'N/A')
        except:
            next_run = 'N/A'
        logging.info(f"  - Job ID: {job.id}, Trigger: {job.trigger}, Next run: {next_run}")
    
    # Удаляем старые задачи, если они есть, чтобы избежать дублирования при перезапуске
    removed_count = 0
    if scheduler.get_job('morning_notification_job'):
        scheduler.remove_job('morning_notification_job')
        removed_count += 1
        logging.info("❌ Удалена задача 'morning_notification_job'")
    if scheduler.get_job('afternoon_notification_job'):
        scheduler.remove_job('afternoon_notification_job')
        removed_count += 1
        logging.info("❌ Удалена задача 'afternoon_notification_job'")
    if scheduler.get_job('evening_notification_job'):
        scheduler.remove_job('evening_notification_job')
        removed_count += 1
        logging.info("❌ Удалена задача 'evening_notification_job'")
    if scheduler.get_job('subscription_reminder_job'):
        scheduler.remove_job('subscription_reminder_job')
        removed_count += 1
        logging.info("❌ Удалена задача 'subscription_reminder_job'")
    if scheduler.get_job('free_period_warning_job'):
        scheduler.remove_job('free_period_warning_job')
        removed_count += 1
        logging.info("❌ Удалена задача 'free_period_warning_job'")
    
    logging.info(f"📊 Удалено старых задач: {removed_count}")

    # Добавляем задачи в планировщик с явными ID
    logging.info("➕ Добавление новых задач в планировщик...")
    
    scheduler.add_job(send_morning_notification, trigger='cron', hour=8, minute=0, args=[bot], timezone='Europe/Moscow', id='morning_notification_job', replace_existing=True)
    logging.info("✅ Добавлена задача 'morning_notification_job' на 08:00 MSK")
    
    scheduler.add_job(send_afternoon_notification, trigger='cron', hour=14, minute=0, args=[bot], timezone='Europe/Moscow', id='afternoon_notification_job', replace_existing=True)
    logging.info("✅ Добавлена задача 'afternoon_notification_job' на 14:00 MSK")
    
    scheduler.add_job(send_evening_notification, trigger='cron', hour=20, minute=0, args=[bot], timezone='Europe/Moscow', id='evening_notification_job', replace_existing=True)
    logging.info("✅ Добавлена задача 'evening_notification_job' на 20:00 MSK")
    
    scheduler.add_job(send_subscription_reminder, trigger='cron', hour=18, minute=0, args=[bot], timezone='Europe/Moscow', id='subscription_reminder_job', replace_existing=True)
    logging.info("✅ Добавлена задача 'subscription_reminder_job' на 18:00 MSK")
    
    scheduler.add_job(send_free_period_ending_notification, trigger='cron', hour=10, minute=0, args=[bot], timezone='Europe/Moscow', id='free_period_warning_job', replace_existing=True)
    logging.info("✅ Добавлена задача 'free_period_warning_job' на 10:00 MSK")
    
    # scheduler.add_job(check_namedays, trigger='cron', hour=7, minute=0, args=(bot,)) # Запускаем проверку именин в 7 утра
    
    # Выводим финальное состояние планировщика
    final_jobs = scheduler.get_jobs()
    logging.info(f"📋 Итого задач в планировщике после добавления: {len(final_jobs)}")
    for job in final_jobs:
        try:
            next_run = getattr(job, 'next_run_time', 'N/A')
        except:
            next_run = 'N/A'
        logging.info(f"  - Job ID: {job.id}, Trigger: {job.trigger}, Next run: {next_run}")

    # Запускаем планировщик, если он еще не запущен
    if not scheduler.running:
        scheduler.start()

    # Применяем мидлварь проверки доступа ко всем сообщениям и колбэкам
    dp.message.middleware(check_access)
    dp.callback_query.middleware(check_access)

    # Подключаем роутеры из handlers постом
    dp.include_router(start.router)
    dp.include_router(settings.router)
    dp.include_router(admin_router)  # админ выше всех
    dp.include_router(subscription_router)  # обработчики подписки через Telegram Payments
    dp.include_router(premium_content.router)
    dp.include_router(free_content.router)
    dp.include_router(favorites.router)
    dp.include_router(callbacks.router)
    dp.include_router(support_handler.router)
    dp.include_router(legal_handler.router)
    dp.include_router(text_handler.router)  # всегда последним!

    # Устанавливаем главное меню
    await set_main_menu(bot)
    
    await dp.start_polling(bot)

# Точка входа
if __name__ == "__main__":
    asyncio.run(main())
