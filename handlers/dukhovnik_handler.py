from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext # Импортируем FSMContext
from utils.html_parser import convert_markdown_to_html # Импортируем convert_markdown_to_html
from core.content_sender import send_and_delete_previous # Импортируем новую централизованную функцию

router = Router()

@router.message(Command("dukhovnik"))
async def show_ai_info_handler(message: Message, bot: Bot, state: FSMContext):
    """Отправляет информационное сообщение о возможности диалога."""
    text = "Я слушаю тебя, друг мой. Расскажи, что тебя волнует? Просто напиши мне свой вопрос или мысль."
    await send_and_delete_previous(
        bot=bot,
        chat_id=message.chat.id,
        state=state,
        text=text,
        show_typing=False,
        delete_previous=False,
        track_last_message=False
    )
