from aiogram import Router, F, Bot
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from core.user_database import get_favorite_messages, remove_favorite_message
from core.content_sender import send_and_delete_previous, send_content_message # Импортируем обе функции
import logging
from datetime import datetime
import os # Импортируем os для работы с путями файлов

router = Router()

FAVORITES_PER_PAGE = 5

def get_favorites_navigation_keyboard(user_id: int, current_page: int) -> InlineKeyboardMarkup:
    favorites = get_favorite_messages(user_id)
    total_pages = (len(favorites) + FAVORITES_PER_PAGE - 1) // FAVORITES_PER_PAGE
    
    buttons = []
    if current_page > 0:
        buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"fav_page_{current_page - 1}"))
    if current_page < total_pages - 1:
        buttons.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"fav_page_{current_page + 1}"))
    
    return InlineKeyboardMarkup(inline_keyboard=[buttons])

def get_favorite_message_keyboard(bot_message_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"fav_delete_{bot_message_id}")]
    ])

@router.message(F.text == "/favorites")
@router.message(F.text == "⭐️ Избранное") # Можно добавить кнопку в меню
async def show_favorites(message: Message, bot: Bot, state: FSMContext):
    user_id = message.from_user.id
    chat_id = message.chat.id
    await state.update_data(favorites_current_page=0) # Сбрасываем страницу при входе
    await send_favorites_page(user_id, chat_id, bot, state, 0, delete_previous=True)

async def send_favorites_page(user_id: int, chat_id: int, bot: Bot, state: FSMContext, page: int, delete_previous: bool = False):
    favorites = get_favorite_messages(user_id)
    
    if not favorites:
        await send_and_delete_previous(
            bot=bot,
            chat_id=chat_id,
            state=state,
            text="Ваш список избранного пуст. 😔",
            show_typing=False
        )
        return

    total_pages = (len(favorites) + FAVORITES_PER_PAGE - 1) // FAVORITES_PER_PAGE
    if page < 0 or page >= total_pages:
        page = 0 # Сбрасываем на первую страницу, если некорректный номер

    start_index = page * FAVORITES_PER_PAGE
    end_index = min(start_index + FAVORITES_PER_PAGE, len(favorites))
    
    messages_to_send = favorites[start_index:end_index]

    # Отправляем заголовок страницы избранного, удаляя предыдущее сообщение бота
    await send_and_delete_previous(
        bot=bot,
        chat_id=chat_id,
        state=state,
        text=f"🌟 <b>Ваше избранное (Страница {page + 1}/{total_pages})</b> 🌟",
        show_typing=False
    )

    for fav_entry in messages_to_send:
        text = fav_entry['content']
        image_name = fav_entry.get('image_name')
        timestamp = datetime.fromisoformat(fav_entry['timestamp']).strftime('%d.%m.%Y %H:%M')
        
        # Добавляем информацию о времени добавления
        formatted_text = f"<i>Добавлено: {timestamp}</i>\n\n{text}"

        # Отправляем каждое избранное сообщение без удаления предыдущего
        await send_content_message(
            bot=bot,
            chat_id=chat_id,
            text=formatted_text,
            image_name=image_name,
            reply_markup=get_favorite_message_keyboard(fav_entry['bot_message_id'])
        )

    # Отправляем кнопки навигации
    if total_pages > 1:
        await bot.send_message(chat_id, "Навигация по избранному:", reply_markup=get_favorites_navigation_keyboard(user_id, page))
    
    await state.update_data(favorites_current_page=page)


@router.callback_query(F.data.startswith('fav_page_'))
async def favorites_page_callback(callback_query: CallbackQuery, bot: Bot, state: FSMContext):
    user_id = callback_query.from_user.id
    chat_id = callback_query.message.chat.id
    new_page = int(callback_query.data.split('_')[2])

    await callback_query.answer() # Убираем "часики" на кнопке
    
    # Удаляем сообщение с предыдущей навигацией, чтобы не засорять чат
    try:
        await bot.delete_message(chat_id=chat_id, message_id=callback_query.message.message_id)
    except Exception as e:
        logging.warning(f"Не удалось удалить сообщение с навигацией по избранному: {e}")

    await send_favorites_page(user_id, chat_id, bot, state, new_page)


@router.callback_query(F.data.startswith('fav_delete_'))
async def delete_favorite_callback(callback_query: CallbackQuery, bot: Bot, state: FSMContext):
    bot_message_id_to_delete = int(callback_query.data.split('_')[2])
    user_id = callback_query.from_user.id
    chat_id = callback_query.message.chat.id

    if remove_favorite_message(user_id, bot_message_id_to_delete):
        await callback_query.answer("Сообщение удалено из избранного! 🗑️")
        # Удаляем сообщение из чата, которое было отображением избранного
        try:
            await bot.delete_message(chat_id=chat_id, message_id=callback_query.message.message_id)
        except Exception as e:
            logging.warning(f"Не удалось удалить сообщение избранного из чата: {e}")
        
        # Перезагружаем текущую страницу избранного
        user_data = await state.get_data()
        current_page = user_data.get('favorites_current_page', 0)
        await send_favorites_page(user_id, chat_id, bot, state, current_page, delete_previous=True)
    else:
        await callback_query.answer("Не удалось удалить сообщение из избранного.", show_alert=True)
