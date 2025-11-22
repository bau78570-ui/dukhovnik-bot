from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from core.content_sender import send_and_delete_previous
import logging

# Создаем роутер для юридических документов
router = Router()

@router.message(Command("documents"))
async def documents_handler(message: Message, bot: Bot, state: FSMContext):
    """
    Обработчик для команды /documents.
    Отправляет сообщение с кнопками для доступа к юридическим документам.
    """
    logging.info("documents_handler called - creating URL buttons")
    
    text = (
        "📑 <b>Юридическая информация</b>\n\n"
        "Нажмите на кнопку, чтобы открыть документ."
    )
    
    # Создаем инлайн-кнопки для документов
    builder = InlineKeyboardBuilder()
    builder.button(text="📄 Публичная оферта", url="https://teletype.in/@doc_content/6QpC1mnksmb")
    builder.button(text="🔒 Политика конфиденциальности", url="https://teletype.in/@doc_content/Hh6yLo5tGOj")
    builder.button(text="🔄 Правила подписки", url="https://teletype.in/@doc_content/sAIM1-NuMBl")
    builder.button(text="👤 Реквизиты Исполнителя", url="https://teletype.in/@doc_content/8-O2LHYxBaV")
    builder.button(text="📄 Условия использования", url="https://teletype.in/@doc_content/IWP-06AxhyO")
    builder.adjust(1)
       
    markup = builder.as_markup()
    logging.info(f"Created markup with {len(markup.inline_keyboard)} rows")
    for i, row in enumerate(markup.inline_keyboard):
        for j, button in enumerate(row):
            logging.info(f"Button {i}-{j}: text='{button.text}', url='{button.url}', callback='{button.callback_data}'")
    
    await send_and_delete_previous(
        bot=bot,
        chat_id=message.chat.id,
        state=state,
        text=text,
        reply_markup=markup,
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
        "Нажмите на кнопку, чтобы открыть документ."
    )
    
    # Создаем инлайн-кнопки для документов
    builder = InlineKeyboardBuilder()
    builder.button(
        text="📄 Публичная оферта",
        url="https://teletype.in/@doc_content/6QpC1mnksmb"
    )
    builder.button(
        text="🔒 Политика конфиденциальности",
        url="https://teletype.in/@doc_content/Hh6yLo5tGOj"
    )
    builder.button(
        text="🔄 Правила подписки",
        url="https://teletype.in/@doc_content/sAIM1-NuMBl"
    )
    builder.button(
        text="👤 Реквизиты Исполнителя",
        url="https://teletype.in/@doc_content/8-O2LHYxBaV"
    )
    builder.button(
        text="📄 Условия использования",
        url="https://teletype.in/@doc_content/IWP-06AxhyO"
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

