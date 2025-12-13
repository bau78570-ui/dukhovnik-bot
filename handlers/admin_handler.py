import os
import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from dotenv import load_dotenv
from core.user_database import get_bot_stats

# Загружаем переменные окружения
load_dotenv()

# Создаем роутер для админ-панели
router = Router()

@router.message(Command("admin"))
async def admin_handler(message: Message):
    """
    Обработчик команды /admin.
    Доступен только для администратора (ID из переменной окружения ADMIN_ID).
    """
    user_id = message.from_user.id
    admin_id_str = os.getenv('ADMIN_ID')
    
    # Логируем для отладки
    logging.info(f"Admin command received from user_id: {user_id}, ADMIN_ID from env: {admin_id_str}")
    
    # Проверяем, является ли пользователь администратором
    if not admin_id_str:
        logging.warning("ADMIN_ID not set in environment variables!")
        await message.answer(
            "❌ Ошибка: переменная ADMIN_ID не установлена в файле .env",
            parse_mode='HTML'
        )
        return
    
    try:
        admin_id = int(admin_id_str)
    except (ValueError, TypeError):
        logging.error(f"ADMIN_ID is not a valid integer: {admin_id_str}")
        await message.answer(
            "❌ Ошибка: неверный формат ADMIN_ID в файле .env",
            parse_mode='HTML'
        )
        return
    
    if user_id != admin_id:
        logging.info(f"Access denied: user_id {user_id} != admin_id {admin_id}")
        # Игнорируем команду от всех, кроме администратора
        return
    
    logging.info(f"Admin access granted for user_id: {user_id}")
    
    try:
        # Получаем статистику
        stats = await get_bot_stats()
        
        # Формируем сообщение со статистикой
        stats_text = (
            f"📊 <b>Статистика Духовника</b>\n\n"
            f"👥 Всего пользователей: {stats['total_users']}\n"
            f"✅ Активных подписок: {stats['active_subscriptions']}"
        )
        
        await message.answer(stats_text, parse_mode='HTML')
        logging.info("Admin stats sent successfully")
    except Exception as e:
        logging.error(f"Error getting bot stats: {e}", exc_info=True)
        await message.answer(
            f"❌ Ошибка при получении статистики: {str(e)}",
            parse_mode='HTML'
        )

