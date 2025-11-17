from collections import defaultdict
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext # Импортируем FSMContext
from core.content_sender import send_and_delete_previous # Импортируем новую централизованную функцию

# --- Имитация базы данных настроек ---
# Используем defaultdict для удобства: если пользователя нет, создаются настройки по умолчанию
user_settings = defaultdict(lambda: {"morning": True, "day": True, "evening": False})

# Создаем роутер для настроек
router = Router()

def get_settings_keyboard(user_id: int) -> InlineKeyboardBuilder:
    """Генерирует инлайн-клавиатуру на основе настроек пользователя."""
    settings = user_settings[user_id]
    builder = InlineKeyboardBuilder()
    
    # Кнопка "Утреннее вдохновение"
    morning_status = "✅" if settings["morning"] else "❌"
    builder.button(
        text=f"[{morning_status}] Утреннее вдохновение",
        callback_data="toggle_morning"
    )
    # Кнопка "Дневные рецепты"
    day_status = "✅" if settings["day"] else "❌"
    builder.button(
        text=f"[{day_status}] Дневные рецепты",
        callback_data="toggle_day"
    )
    # Кнопка "Вечерние размышления"
    evening_status = "✅" if settings["evening"] else "❌"
    builder.button(
        text=f"[{evening_status}] Вечерние размышления",
        callback_data="toggle_evening"
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
        show_typing=False
    )

@router.callback_query(F.data.startswith("toggle_"))
async def toggle_settings_handler(callback: CallbackQuery):
    """
    Обрабатывает нажатия на кнопки настроек.
    """
    user_id = callback.from_user.id
    # Получаем тип настройки из callback_data (например, "morning")
    setting_type = callback.data.split("_")[1]

    # Инвертируем значение настройки (True -> False, False -> True)
    user_settings[user_id][setting_type] = not user_settings[user_id][setting_type]

    # Обновляем клавиатуру в существующем сообщении
    await callback.message.edit_reply_markup(
        reply_markup=get_settings_keyboard(user_id).as_markup()
    )

    # Показываем всплывающее уведомление
    await callback.answer("Настройки сохранены!")
