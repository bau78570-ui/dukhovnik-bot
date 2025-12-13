import os
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from core.user_database import user_db
from core.subscription_checker import is_subscription_active

# Создаем роутер для админ-панели
router = Router()

def get_admin_id():
    """Получает ADMIN_ID из переменных окружения (загружает каждый раз)"""
    return os.getenv('ADMIN_ID')

@router.message(Command("admin") | (F.text == "/admin"))
async def admin_command_handler(message: Message):
    """
    Обработчик команды /admin.
    Доступен ТОЛЬКО для администратора (ID из переменной окружения ADMIN_ID).
    """
    user_id = message.from_user.id
    ADMIN_ID = get_admin_id()
    
    # Логируем попытку доступа
    logging.info(f"=== ADMIN COMMAND ATTEMPT ===")
    logging.info(f"User ID: {user_id}")
    logging.info(f"ADMIN_ID from env: {ADMIN_ID}")
    logging.info(f"Message text: {message.text}")
    
    # Проверка 1: Проверяем, установлен ли ADMIN_ID
    if not ADMIN_ID:
        logging.error("ADMIN_ID not set in .env file!")
        await message.answer(
            "❌ <b>Ошибка конфигурации</b>\n\n"
            "Переменная ADMIN_ID не установлена в файле .env",
            parse_mode='HTML'
        )
        return
    
    # Проверка 2: Проверяем формат ADMIN_ID
    try:
        admin_id = int(ADMIN_ID)
    except (ValueError, TypeError):
        logging.error(f"ADMIN_ID is not a valid integer: {ADMIN_ID}")
        await message.answer(
            "❌ <b>Ошибка конфигурации</b>\n\n"
            f"Неверный формат ADMIN_ID в файле .env: {ADMIN_ID}",
            parse_mode='HTML'
        )
        return
    
    # Проверка 3: Проверяем, является ли пользователь администратором
    if user_id != admin_id:
        logging.warning(f"Access denied: user_id {user_id} != admin_id {admin_id}")
        # Молча игнорируем команду от не-администраторов
        return
    
    # Все проверки пройдены - пользователь является администратором
    logging.info(f"Admin access granted for user_id: {user_id}")
    
    try:
        # Получаем статистику
        # 1. Общее количество пользователей (все, кто хотя бы раз нажал /start)
        total_users = len(user_db)
        
        # 2. Количество активных платных подписок
        active_subscriptions = 0
        for user_id_in_db in user_db.keys():
            if await is_subscription_active(user_id_in_db):
                active_subscriptions += 1
        
        # Формируем сообщение со статистикой
        stats_text = (
            f"📊 <b>Статистика Духовника</b>\n\n"
            f"👥 <b>Всего пользователей:</b> {total_users}\n"
            f"✅ <b>Активных подписок:</b> {active_subscriptions}"
        )
        
        await message.answer(stats_text, parse_mode='HTML')
        logging.info(f"Admin stats sent: total_users={total_users}, active_subscriptions={active_subscriptions}")
        
    except Exception as e:
        logging.error(f"Error getting bot stats: {e}", exc_info=True)
        await message.answer(
            f"❌ <b>Ошибка при получении статистики</b>\n\n"
            f"Детали: {str(e)}",
            parse_mode='HTML'
        )
