import os
import logging
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from core.user_database import user_db, get_user
from core.subscription_checker import is_subscription_active, activate_premium_subscription, is_trial_active

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
        [InlineKeyboardButton(text="🔎 Статус подписки", callback_data="admin_check_subscription")],
        [InlineKeyboardButton(text="⭐ Активировать Premium", callback_data="admin_activate_premium")],
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
        "<code>/support_reply &lt;user_id&gt; &lt;текст&gt;</code>\n"
        "<code>/admin_activate_premium &lt;user_id&gt; [days]</code>\n"
        "<code>/admin_check_subscription &lt;user_id&gt;</code>"
    )
    await message.answer(menu_text, parse_mode='HTML', reply_markup=build_admin_menu())

@router.message(Command("admin_stats"), F.chat.type == "private")
async def admin_stats_handler(message: Message):
    """Показывает статистику бота с детальным списком активных подписок (только для админа)."""
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
        
        # Собираем информацию об активных подписках
        active_subscriptions = []
        active_trials = 0
        
        for user_id_in_db in user_db.keys():
            user_data = user_db[user_id_in_db]
            
            # Проверяем активную подписку
            if await is_subscription_active(user_id_in_db):
                sub_end = user_data.get('subscription_end_date')
                sub_end_str = sub_end.strftime('%d.%m.%Y') if hasattr(sub_end, 'strftime') else str(sub_end)
                
                # Определяем вид подписки по истории платежей
                payments = user_data.get('payments', [])
                subscription_type = "неизвестно"
                receipt_sent = "нет данных"
                
                if payments:
                    last_payment = payments[-1]
                    period = last_payment.get('period', 'неизвестно')
                    subscription_type = period
                    # Проверяем, был ли чек направлен (если payment содержит payload, значит чек был сформирован)
                    payload = last_payment.get('payload', '')
                    receipt_sent = "✅ да" if payload else "❓ не подтверждено"
                
                active_subscriptions.append({
                    'user_id': user_id_in_db,
                    'end_date': sub_end_str,
                    'type': subscription_type,
                    'receipt': receipt_sent
                })
            
            # Подсчитываем активные пробные периоды
            if await is_trial_active(user_id_in_db):
                active_trials += 1
        
        # Формируем основную статистику
        stats_text = (
            f"📊 <b>Статистика Духовника</b>\n\n"
            f"👥 <b>Всего пользователей:</b> {total_users}\n"
            f"✅ <b>Активных подписок:</b> {len(active_subscriptions)}\n"
            f"🧪 <b>Активных пробных периодов:</b> {active_trials}\n"
        )
        
        # Добавляем детальный список активных подписок
        if active_subscriptions:
            stats_text += "\n━━━━━━━━━━━━━━━━━━━━━\n"
            stats_text += "<b>📋 Детали активных подписок:</b>\n\n"
            
            for sub in active_subscriptions:
                stats_text += (
                    f"👤 <b>ID:</b> <code>{sub['user_id']}</code>\n"
                    f"📅 <b>До:</b> {sub['end_date']}\n"
                    f"💳 <b>Тип:</b> {sub['type']}\n"
                    f"🧾 <b>Чек:</b> {sub['receipt']}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                )
        
        await message.answer(stats_text, parse_mode='HTML')
        logging.info(f"Admin stats sent: total_users={total_users}, active_subscriptions={len(active_subscriptions)}, active_trials={active_trials}")
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

@router.callback_query(F.data == "admin_check_subscription")
async def admin_check_subscription_callback(query: CallbackQuery):
    if not is_admin(query.from_user.id):
        await query.answer("Доступ запрещён", show_alert=True)
        return
    text = "Команда: /admin_check_subscription <user_id>"
    await query.message.answer(text)
    await query.answer()

@router.callback_query(F.data == "admin_activate_premium")
async def admin_activate_premium_callback(query: CallbackQuery):
    if not is_admin(query.from_user.id):
        await query.answer("Доступ запрещён", show_alert=True)
        return
    text = "Команда: /admin_activate_premium <user_id> [days]"
    await query.message.answer(text)
    await query.answer()

@router.callback_query(F.data == "admin_menu_close")
async def admin_menu_close_callback(query: CallbackQuery):
    if not is_admin(query.from_user.id):
        await query.answer("Доступ запрещён", show_alert=True)
        return
    await query.message.edit_reply_markup(reply_markup=None)
    await query.answer()

@router.message(Command("admin_activate_premium"), F.chat.type == "private")
async def admin_activate_premium_handler(message: Message):
    """Ручная активация премиума: /admin_activate_premium <user_id> [days]."""
    if not is_admin(message.from_user.id):
        await message.answer("Доступ запрещён", parse_mode='HTML')
        return
    parts = message.text.split() if message.text else []
    if len(parts) < 2:
        await message.answer("Формат: /admin_activate_premium <user_id> [days]")
        return
    try:
        user_id = int(parts[1])
    except ValueError:
        await message.answer("Неверный user_id. Формат: /admin_activate_premium <user_id> [days]")
        return
    days = 30
    if len(parts) >= 3:
        try:
            days = max(1, min(3650, int(parts[2])))
        except ValueError:
            await message.answer("Неверное число дней. Пример: /admin_activate_premium 123456 30")
            return

    success = await activate_premium_subscription(user_id, duration_days=days)
    if success:
        payment_logger = logging.getLogger("payments")
        payment_logger.info(f"MANUAL_ACTIVATE user_id={user_id} days={days}")
        await message.answer(f"✅ Premium активирован для user_id {user_id} на {days} дней.")
    else:
        await message.answer("❌ Не удалось активировать Premium. Проверьте логи.")

@router.message(Command("admin_check_subscription"), F.chat.type == "private")
async def admin_check_subscription_handler(message: Message):
    """Проверка статуса подписки: /admin_check_subscription <user_id>."""
    if not is_admin(message.from_user.id):
        await message.answer("Доступ запрещён", parse_mode='HTML')
        return
    parts = message.text.split() if message.text else []
    if len(parts) < 2:
        await message.answer("Формат: /admin_check_subscription <user_id>")
        return
    try:
        user_id = int(parts[1])
    except ValueError:
        await message.answer("Неверный user_id. Формат: /admin_check_subscription <user_id>")
        return

    user_data = get_user(user_id)
    status = user_data.get('status', 'free')
    trial_active = await is_trial_active(user_id)
    sub_active = await is_subscription_active(user_id)
    trial_start = user_data.get('trial_start_date')
    sub_end = user_data.get('subscription_end_date')
    trial_start_str = trial_start.isoformat() if hasattr(trial_start, "isoformat") else (str(trial_start) if trial_start else "нет")
    sub_end_str = sub_end.isoformat() if hasattr(sub_end, "isoformat") else (str(sub_end) if sub_end else "нет")

    text = (
        f"👤 <b>User ID:</b> {user_id}\n"
        f"🏷️ <b>Статус:</b> {status}\n"
        f"🧪 <b>Пробный активен:</b> {trial_active}\n"
        f"💳 <b>Подписка активна:</b> {sub_active}\n"
        f"📅 <b>Дата старта пробного:</b> {trial_start_str}\n"
        f"📆 <b>Дата окончания подписки:</b> {sub_end_str}"
    )
    await message.answer(text, parse_mode='HTML')