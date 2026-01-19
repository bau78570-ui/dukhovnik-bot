import os
import logging
from aiogram import Router, F, Bot
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ParseMode
from utils.html_parser import convert_markdown_to_html
from core.support_history import add_support_entry, get_support_history, set_support_status, get_support_status

# Создаем состояния для диалога поддержки
class SupportState(StatesGroup):
    waiting_for_message = State()

router = Router()
support_message_map: dict[int, int] = {}

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
    username = message.from_user.username
    first_name = message.from_user.first_name

    admin_ticket_text = (
        "🆘 <b>Новое обращение в поддержку</b>\n\n"
        f"👤 <b>Имя:</b> {display_name}\n"
        f"🔗 <b>Username:</b> {('@' + username) if username else 'не указан'}\n"
        f"🆔 <b>User ID:</b> {user_id}\n\n"
        "Ответьте <b>reply</b> на пересланное сообщение или используйте:\n"
        f"<code>/support_reply {user_id} ваш_ответ</code>"
    )
    await bot.send_message(admin_id, admin_ticket_text, parse_mode=ParseMode.HTML)

    forwarded = await bot.forward_message(
        chat_id=admin_id,
        from_chat_id=message.chat.id,
        message_id=message.message_id
    )
    support_message_map[forwarded.message_id] = user_id
    logging.info(f"Сообщение от user_id {user_id} пересланное админу {ADMIN_ID}")
    logging.info(f"Support message from {display_name} (user_id {user_id})")
    set_support_status(user_id, "новый")
    add_support_entry(
        user_id=user_id,
        direction="user",
        text=message.text,
        content_type=message.content_type,
        username=username,
        first_name=first_name,
        message_id=message.message_id
    )

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
    username = message.from_user.username
    first_name = message.from_user.first_name

    admin_ticket_text = (
        "🆘 <b>Новое обращение в поддержку</b>\n\n"
        f"👤 <b>Имя:</b> {display_name}\n"
        f"🔗 <b>Username:</b> {('@' + username) if username else 'не указан'}\n"
        f"🆔 <b>User ID:</b> {user_id}\n\n"
        "Ответьте <b>reply</b> на пересланное сообщение или используйте:\n"
        f"<code>/support_reply {user_id} ваш_ответ</code>"
    )
    await bot.send_message(admin_id, admin_ticket_text, parse_mode=ParseMode.HTML)

    forwarded = await bot.forward_message(
        chat_id=admin_id,
        from_chat_id=message.chat.id,
        message_id=message.message_id
    )
    support_message_map[forwarded.message_id] = user_id
    logging.info(f"Сообщение от user_id {user_id} пересланное админу {ADMIN_ID}")
    logging.info(f"Support message from {display_name} (user_id {user_id})")
    set_support_status(user_id, "новый")
    add_support_entry(
        user_id=user_id,
        direction="user",
        text=None,
        content_type=message.content_type,
        username=username,
        first_name=first_name,
        message_id=message.message_id
    )

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
    replied_message_id = message.reply_to_message.message_id
    user_id = support_message_map.get(replied_message_id)
    if not user_id and message.reply_to_message.forward_from:
        user_id = message.reply_to_message.forward_from.id
    if not user_id:
        await bot.send_message(admin_id, "Не удалось определить пользователя для ответа.")
        return
    response_text = "Ответ от поддержки: " + (message.text or "")
    await bot.send_message(user_id, response_text)
    set_support_status(user_id, "в работе")
    add_support_entry(
        user_id=user_id,
        direction="admin",
        text=message.text,
        content_type=message.content_type,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        message_id=message.message_id
    )

@router.message(Command("support_reply"))
async def support_reply_command(message: Message, bot: Bot):
    """Ответ админу без reply: /support_reply <user_id> <text>."""
    ADMIN_ID = os.getenv("ADMIN_ID")
    if not ADMIN_ID:
        return
    try:
        admin_id = int(ADMIN_ID)
    except ValueError:
        return
    if message.from_user.id != admin_id:
        return

    parts = message.text.split(maxsplit=2) if message.text else []
    if len(parts) < 3:
        await message.answer("Формат: /support_reply <user_id> <текст ответа>")
        return
    try:
        user_id = int(parts[1])
    except ValueError:
        await message.answer("Неверный user_id. Формат: /support_reply <user_id> <текст ответа>")
        return

    response_text = "Ответ от поддержки: " + parts[2]
    await bot.send_message(user_id, response_text)
    set_support_status(user_id, "в работе")
    add_support_entry(
        user_id=user_id,
        direction="admin",
        text=parts[2],
        content_type=message.content_type,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        message_id=message.message_id
    )

@router.message(Command("support_history"))
async def support_history_command(message: Message, bot: Bot):
    """Показывает историю переписки: /support_history <user_id> [limit]."""
    ADMIN_ID = os.getenv("ADMIN_ID")
    if not ADMIN_ID:
        return
    try:
        admin_id = int(ADMIN_ID)
    except ValueError:
        return
    if message.from_user.id != admin_id:
        return

    parts = message.text.split() if message.text else []
    if len(parts) < 2:
        await message.answer("Формат: /support_history <user_id> [limit]")
        return
    try:
        user_id = int(parts[1])
    except ValueError:
        await message.answer("Неверный user_id. Формат: /support_history <user_id> [limit]")
        return
    limit = 20
    if len(parts) >= 3:
        try:
            limit = max(1, min(100, int(parts[2])))
        except ValueError:
            await message.answer("Неверный limit. Пример: /support_history 123456 20")
            return

    history = get_support_history(user_id)
    if not history:
        await message.answer(f"История для user_id {user_id} пуста.")
        return
    status = get_support_status(user_id)
    entries = history[-limit:]
    lines = [f"🧾 <b>История поддержки</b> (user_id {user_id})", f"🏷️ <b>Статус:</b> {status}", ""]
    for entry in entries:
        direction = "Пользователь" if entry.get("direction") == "user" else "Поддержка"
        text = entry.get("text") or f"[{entry.get('content_type', 'message')}]"
        timestamp = entry.get("timestamp", "")
        lines.append(f"• <b>{direction}</b> ({timestamp}): {text}")
    await message.answer("\n".join(lines), parse_mode=ParseMode.HTML)

@router.message(Command("support_status"))
async def support_status_command(message: Message, bot: Bot):
    """Устанавливает статус тикета: /support_status <user_id> <новый|в работе|закрыт>."""
    ADMIN_ID = os.getenv("ADMIN_ID")
    if not ADMIN_ID:
        return
    try:
        admin_id = int(ADMIN_ID)
    except ValueError:
        return
    if message.from_user.id != admin_id:
        return

    parts = message.text.split(maxsplit=2) if message.text else []
    if len(parts) < 3:
        await message.answer("Формат: /support_status <user_id> <новый|в работе|закрыт>")
        return
    try:
        user_id = int(parts[1])
    except ValueError:
        await message.answer("Неверный user_id. Формат: /support_status <user_id> <новый|в работе|закрыт>")
        return
    status = parts[2].strip().lower()
    allowed = {"новый", "в работе", "закрыт"}
    if status not in allowed:
        await message.answer("Статус должен быть: новый | в работе | закрыт")
        return
    set_support_status(user_id, status)
    await message.answer(f"Статус для user_id {user_id} установлен: {status}")
