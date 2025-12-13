import os
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
    # Проверяем, является ли пользователь администратором
    admin_id = os.getenv('ADMIN_ID')
    if not admin_id or message.from_user.id != int(admin_id):
        # Игнорируем команду от всех, кроме администратора
        return
    
    # Получаем статистику
    stats = await get_bot_stats()
    
    # Формируем сообщение со статистикой
    stats_text = (
        f"📊 <b>Статистика Духовника</b>\n\n"
        f"👥 Всего пользователей: {stats['total_users']}\n"
        f"✅ Активных подписок: {stats['active_subscriptions']}"
    )
    
    await message.answer(stats_text, parse_mode='HTML')

