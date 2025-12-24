import os
from aiogram import Router, F, Bot
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ParseMode
from utils.html_parser import convert_markdown_to_html

# Создаем состояния для диалога поддержки
class SupportState(StatesGroup):
    waiting_for_message = State()

router = Router()

@router.message(Command("support"))
async def support_start(message: Message, state: FSMContext):
    """Начинает диалог техподдержки."""
    await state.set_state(SupportState.waiting_for_message)
    text = (
        "📝 **Связь с разработчиком**\n\n"
        "Пожалуйста, опиши свой вопрос, проблему или предложение одним сообщением. Я получу его и отвечу, как только смогу.\n\n"
        "Чтобы отменить, просто нажми /start."
    )
    html_text = convert_markdown_to_html(text)
    await message.answer(html_text, parse_mode=ParseMode.HTML)

@router.message(StateFilter(SupportState.waiting_for_message), F.text)
async def support_message_received(message: Message, state: FSMContext, bot: Bot):
    """Получает сообщение пользователя и пересылает его админу."""
    # Пропускаем команды - они должны обрабатываться другими обработчиками
    if message.text and message.text.strip().startswith('/'):
        return
    
    await state.clear() # Сбрасываем состояние
    
    ADMIN_ID = os.getenv("ADMIN_ID")
    if not ADMIN_ID:
        await message.answer("Ошибка: не удалось связаться с поддержкой. Разработчик уже уведомлен.")
        return

    # Формируем красивое сообщение для админа
    user_info = f"👤 от @{message.from_user.username} (ID: {message.from_user.id})"
    admin_text = f"🆘 **Новое обращение в поддержку!**\n\n{user_info}\n\n**Сообщение:**\n{message.text}"
    admin_html_text = convert_markdown_to_html(admin_text)
    await bot.send_message(
        chat_id=ADMIN_ID,
        text=admin_html_text,
        parse_mode=ParseMode.HTML
    )
    
    # Отвечаем пользователю
    user_text = (
        "✅ **Сообщение отправлено!**\n\n"
        "Спасибо за обратную связь. Я скоро изучу твое сообщение."
    )
    user_html_text = convert_markdown_to_html(user_text)
    await message.answer(user_html_text, parse_mode=ParseMode.HTML)

@router.message(StateFilter(SupportState.waiting_for_message))
async def support_invalid_message(message: Message):
    """Если пользователь прислал не текст (фото, стикер)."""
    text = "Пожалуйста, опиши свою проблему **текстовым сообщением**."
    html_text = convert_markdown_to_html(text)
    await message.answer(html_text, parse_mode=ParseMode.HTML)
