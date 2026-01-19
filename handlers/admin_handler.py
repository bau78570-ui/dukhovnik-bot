import os
import logging
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from core.user_database import user_db
from core.subscription_checker import is_subscription_active

# Создаем роутер для админ-панели
router = Router()

def get_admin_id():
    """Получает ADMIN_ID из переменных окружения (загружает каждый раз)"""
    return os.getenv('ADMIN_ID')

def is_admin(user_id: int) -> bool:
    ADMIN_ID = get_admin_id()
    try:
        return ADMIN_ID is not None and int(ADMIN_ID) == user_id
    except (ValueError, TypeError):
        return False

def build_admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🧾 История поддержки", callback_data="admin_support_history")],
        [InlineKeyboardButton(text="🏷️ Статус тикета", callback_data="admin_support_status")],
        [InlineKeyboardButton(text="✉️ Ответить пользователю", callback_data="admin_support_reply")],
        [InlineKeyboardButton(text="❌ Закрыть меню", callback_data="admin_menu_close")]
    ])

@router.message(Command("admin"), F.chat.type == "private")
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
        await message.answer("Доступ запрещён", parse_mode='HTML')
        return
    
    # Все проверки пройдены - пользователь является администратором
    logging.info(f"Admin access granted for user_id: {user_id}")
    menu_text = (
        "🛠️ <b>Admin меню</b>\n\n"
        "Здесь собраны функции поддержки и статистики.\n"
        "Выберите действие или используйте команды:\n"
        "<code>/admin_stats</code>\n"
        "<code>/support_history &lt;user_id&gt; [limit]</code>\n"
        "<code>/support_status &lt;user_id&gt; &lt;новый|в работе|закрыт&gt;</code>\n"
        "<code>/support_reply &lt;user_id&gt; &lt;текст&gt;</code>"
    )
    await message.answer(menu_text, parse_mode='HTML', reply_markup=build_admin_menu())

@router.message(Command("admin_stats"), F.chat.type == "private")
async def admin_stats_handler(message: Message):
    """Показывает статистику бота (только для админа)."""
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("Доступ запрещён", parse_mode='HTML')
        return
    try:
        total_users = len(user_db)
        if total_users == 0:
            await message.answer(
                "📊 <b>Статистика Духовника</b>\n\n"
                "⚠️ База пользователей пуста. Проверьте /start",
                parse_mode='HTML'
            )
            logging.info("Admin stats: user_db is empty")
            return
        active_subscriptions = 0
        for user_id_in_db in user_db.keys():
            if await is_subscription_active(user_id_in_db):
                active_subscriptions += 1
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

@router.callback_query(F.data == "admin_stats")
async def admin_stats_callback(query: CallbackQuery):
    await admin_stats_handler(query.message)
    await query.answer()

@router.callback_query(F.data == "admin_support_history")
async def admin_support_history_callback(query: CallbackQuery):
    if not is_admin(query.from_user.id):
        await query.answer("Доступ запрещён", show_alert=True)
        return
    text = "Команда: /support_history <user_id> [limit]"
    await query.message.answer(text)
    await query.answer()

@router.callback_query(F.data == "admin_support_status")
async def admin_support_status_callback(query: CallbackQuery):
    if not is_admin(query.from_user.id):
        await query.answer("Доступ запрещён", show_alert=True)
        return
    text = "Команда: /support_status <user_id> <новый|в работе|закрыт>"
    await query.message.answer(text)
    await query.answer()

@router.callback_query(F.data == "admin_support_reply")
async def admin_support_reply_callback(query: CallbackQuery):
    if not is_admin(query.from_user.id):
        await query.answer("Доступ запрещён", show_alert=True)
        return
    text = "Команда: /support_reply <user_id> <текст ответа>"
    await query.message.answer(text)
    await query.answer()

@router.callback_query(F.data == "admin_menu_close")
async def admin_menu_close_callback(query: CallbackQuery):
    if not is_admin(query.from_user.id):
        await query.answer("Доступ запрещён", show_alert=True)
        return
    await query.message.edit_reply_markup(reply_markup=None)
    await query.answer()