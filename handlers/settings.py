from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext # Импортируем FSMContext
from core.content_sender import send_and_delete_previous # Импортируем новую централизованную функцию
from core.user_database import get_user, save_user_db

# Создаем роутер для настроек
router = Router()

def get_settings_keyboard(user_id: int) -> InlineKeyboardBuilder:
    """Генерирует инлайн-клавиатуру на основе настроек пользователя."""
    user_data = get_user(user_id)
    settings = user_data.get('notifications', {'morning': True, 'daily': True, 'evening': True})
    builder = InlineKeyboardBuilder()
    
    # Кнопка "Утреннее уведомление"
    morning_status = "✅" if settings.get("morning", True) else "❌"
    builder.button(
        text=f"{morning_status} Утреннее уведомление",
        callback_data="toggle_morning"
    )
    # Кнопка "Слово Дня"
    daily_status = "✅" if settings.get("daily", True) else "❌"
    builder.button(
        text=f"{daily_status} Слово Дня (14:00)",
        callback_data="toggle_daily"
    )
    # Кнопка "Вечернее размышление"
    evening_status = "✅" if settings.get("evening", True) else "❌"
    builder.button(
        text=f"{evening_status} Вечернее размышление",
        callback_data="toggle_evening"
    )
    
    # Кнопка "Документы"
    builder.button(
        text="📑 Документы",
        callback_data="open_docs"
    )
    
    builder.adjust(1) # Все кнопки в один столбец
    return builder

@router.message(Command("settings"))
async def settings_handler(message: Message, bot: Bot, state: FSMContext):
    """
    Обработчик для команды /settings.
    Отправляет сообщение с настройками уведомлений.
    """
    user_id = message.from_user.id
    text = "⚙️ <b>Настройки уведомлений</b>\n\nЗдесь вы можете выбрать, какие ежедневные сообщения вы хотите получать. Ваше спокойствие — наш главный приоритет!"
    
    await send_and_delete_previous(
        bot=bot,
        chat_id=message.chat.id,
        state=state,
        text=text,
        reply_markup=get_settings_keyboard(user_id).as_markup(),
        show_typing=False,
        delete_previous=False,
        track_last_message=False
    )

@router.callback_query(F.data.startswith("toggle_"))
async def toggle_settings_handler(callback: CallbackQuery):
    """
    Обрабатывает нажатия на кнопки настроек.
    """
    user_id = callback.from_user.id
    # Получаем тип настройки из callback_data (например, "morning", "daily", "evening")
    setting_type = callback.data.split("_")[1]

    # Получаем данные пользователя
    user_data = get_user(user_id)
    if 'notifications' not in user_data:
        user_data['notifications'] = {'morning': True, 'daily': True, 'evening': True}
    
    # Инвертируем значение настройки (True -> False, False -> True)
    user_data['notifications'][setting_type] = not user_data['notifications'].get(setting_type, True)
    
    # Сохраняем в базу
    save_user_db()

    # Обновляем клавиатуру в существующем сообщении
    await callback.message.edit_reply_markup(
        reply_markup=get_settings_keyboard(user_id).as_markup()
    )

    # Показываем всплывающее уведомление
    await callback.answer("Настройки сохранены!")
