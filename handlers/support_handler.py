import os
import logging
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

@router.message(StateFilter(SupportState.waiting_for_message), F.text & ~F.text.startswith('/'))
async def support_message_received(message: Message, state: FSMContext, bot: Bot):
    """Получает сообщение пользователя и пересылает его админу."""
    await state.clear() # Сбрасываем состояние
    
    ADMIN_ID = os.getenv("ADMIN_ID")
    if not ADMIN_ID:
        await message.answer("Ошибка: не удалось связаться с поддержкой. Разработчик уже уведомлен.")
        return
    try:
        admin_id = int(ADMIN_ID)
    except ValueError:
        await message.answer("Ошибка: не удалось связаться с поддержкой. Разработчик уже уведомлен.")
        return

    display_name = message.from_user.username or message.from_user.first_name or "Аноним"
    user_id = message.from_user.id

    await bot.forward_message(
        chat_id=admin_id,
        from_chat_id=message.chat.id,
        message_id=message.message_id
    )
    logging.info(f"Сообщение от user_id {user_id} пересланное админу {ADMIN_ID}")
    logging.info(f"Support message from {display_name} (user_id {user_id})")

    # Отвечаем пользователю
    user_text = (
        "✅ **Сообщение отправлено!**\n\n"
        "Спасибо за обратную связь. Я скоро изучу твое сообщение."
    )
    user_html_text = convert_markdown_to_html(user_text)
    await message.answer(user_html_text, parse_mode=ParseMode.HTML)

@router.message(StateFilter(SupportState.waiting_for_message), ~F.text)
async def support_message_received_non_text(message: Message, state: FSMContext, bot: Bot):
    """Получает сообщение пользователя (не текст) и пересылает его админу."""
    await state.clear()

    ADMIN_ID = os.getenv("ADMIN_ID")
    if not ADMIN_ID:
        await message.answer("Ошибка: не удалось связаться с поддержкой. Разработчик уже уведомлен.")
        return
    try:
        admin_id = int(ADMIN_ID)
    except ValueError:
        await message.answer("Ошибка: не удалось связаться с поддержкой. Разработчик уже уведомлен.")
        return

    display_name = message.from_user.username or message.from_user.first_name or "Аноним"
    user_id = message.from_user.id

    await bot.forward_message(
        chat_id=admin_id,
        from_chat_id=message.chat.id,
        message_id=message.message_id
    )
    logging.info(f"Сообщение от user_id {user_id} пересланное админу {ADMIN_ID}")
    logging.info(f"Support message from {display_name} (user_id {user_id})")

    user_text = (
        "✅ **Сообщение отправлено!**\n\n"
        "Спасибо за обратную связь. Я скоро изучу твое сообщение."
    )
    user_html_text = convert_markdown_to_html(user_text)
    await message.answer(user_html_text, parse_mode=ParseMode.HTML)

@router.message(F.reply_to_message)
async def support_admin_reply(message: Message, bot: Bot):
    """Пересылает ответ админа пользователю, если это ответ на пересланное сообщение."""
    ADMIN_ID = os.getenv("ADMIN_ID")
    if not ADMIN_ID:
        return
    try:
        admin_id = int(ADMIN_ID)
    except ValueError:
        return
    if message.from_user.id != admin_id:
        return
    if not message.reply_to_message:
        return
    if not message.reply_to_message.from_user or message.reply_to_message.from_user.id != bot.id:
        return
    if not message.reply_to_message.forward_from:
        await bot.send_message(admin_id, "Не удалось определить пользователя для ответа.")
        return

    user_id = message.reply_to_message.forward_from.id
    await bot.send_message(user_id, "Ответ от поддержки: " + (message.text or ""))
