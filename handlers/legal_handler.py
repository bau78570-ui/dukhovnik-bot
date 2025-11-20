from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from core.content_sender import send_and_delete_previous

# Создаем роутер для юридических документов
router = Router()

@router.message(Command("documents"))
async def documents_handler(message: Message, bot: Bot, state: FSMContext):
    """
    Обработчик для команды /documents.
    Отправляет сообщение с кнопками для доступа к юридическим документам.
    """
    text = (
        "📑 <b>Юридическая информация</b>\n\n"
        "Здесь вы можете ознакомиться с правилами сервиса."
    )
    
    # Создаем инлайн-кнопки с URL-ссылками
    builder = InlineKeyboardBuilder()
    builder.button(
        text="📄 Публичная оферта",
        url="https://www.google.com"  # Заглушка
    )
    builder.button(
        text="🔒 Политика конфиденциальности",
        url="https://www.google.com"  # Заглушка
    )
    builder.button(
        text="🔄 Правила подписки",
        url="https://www.google.com"  # Заглушка
    )
    builder.button(
        text="👤 Реквизиты",
        url="https://www.google.com"  # Заглушка
    )
    builder.adjust(1)  # Все кнопки в один столбец
    
    await send_and_delete_previous(
        bot=bot,
        chat_id=message.chat.id,
        state=state,
        text=text,
        reply_markup=builder.as_markup(),
        show_typing=False
    )

@router.callback_query(F.data == "open_docs")
async def open_docs_callback(callback: CallbackQuery, bot: Bot, state: FSMContext):
    """
    Обработчик для колбэка open_docs.
    Отправляет сообщение с кнопками для доступа к юридическим документам.
    """
    text = (
        "📑 <b>Юридическая информация</b>\n\n"
        "Здесь вы можете ознакомиться с правилами сервиса."
    )
    
    # Создаем инлайн-кнопки с URL-ссылками
    builder = InlineKeyboardBuilder()
    builder.button(
        text="📄 Публичная оферта",
        url="https://www.google.com"  # Заглушка
    )
    builder.button(
        text="🔒 Политика конфиденциальности",
        url="https://www.google.com"  # Заглушка
    )
    builder.button(
        text="🔄 Правила подписки",
        url="https://www.google.com"  # Заглушка
    )
    builder.button(
        text="👤 Реквизиты",
        url="https://www.google.com"  # Заглушка
    )
    builder.adjust(1)  # Все кнопки в один столбец
    
    # Отвечаем на колбэк
    await callback.answer()
    
    # Отправляем сообщение
    await send_and_delete_previous(
        bot=bot,
        chat_id=callback.message.chat.id,
        state=state,
        text=text,
        reply_markup=builder.as_markup(),
        show_typing=False
    )

