from aiogram import Router, F, Bot
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext # Импортируем FSMContext
from core.ai_interaction import get_ai_response
from states import PrayerState # Импортируем состояния
from core.calendar_data import get_calendar_data
import logging # Импортируем logging
from datetime import datetime, timedelta
import asyncio
import os # Импортируем os для работы с путями файлов
import random # Импортируем random для выбора случайного изображения
from core.content_sender import send_and_delete_previous # Импортируем новую централизованную функцию
from utils.html_parser import convert_markdown_to_html # Импортируем convert_markdown_to_html
from core.user_database import add_favorite_message, get_favorite_messages, remove_favorite_message, get_user, save_user_db # Импортируем функции для избранного и user_db

# Создаем роутер для этого обработчика
router = Router()

# Константы для управления историей диалога
MAX_CONVERSATION_HISTORY = 10  # Максимальное количество пар сообщений (user + assistant) в истории
CONVERSATION_TIMEOUT_HOURS = 1  # Таймаут для очистки старой истории (в часах)

def get_conversation_history(user_id: int) -> list:
    """
    Получает историю диалога пользователя, очищает устаревшую историю.
    Возвращает список сообщений в формате [{«role»: «user»/«assistant», «content»: «...»}, ...]
    """
    user_data = get_user(user_id)
    history = user_data.get('conversation_history', [])
    last_message_time = user_data.get('last_message_time')
    
    # Проверяем таймаут - если последнее сообщение было давно, очищаем историю
    if last_message_time:
        try:
            if isinstance(last_message_time, str):
                last_time = datetime.fromisoformat(last_message_time)
            else:
                last_time = last_message_time
            
            if datetime.now() - last_time > timedelta(hours=CONVERSATION_TIMEOUT_HOURS):
                logging.info(f"Очистка устаревшей истории диалога для user_id={user_id} (таймаут {CONVERSATION_TIMEOUT_HOURS}ч)")
                return []  # Возвращаем пустую историю
        except Exception as e:
            logging.error(f"Ошибка при проверке таймаута истории для user_id={user_id}: {e}")
    
    # Ограничиваем количество сообщений в истории (берем последние N*2)
    max_messages = MAX_CONVERSATION_HISTORY * 2  # *2 потому что каждая пара - это user + assistant
    if len(history) > max_messages:
        history = history[-max_messages:]
    
    return history

def save_conversation_history(user_id: int, user_message: str, ai_response: str):
    """
    Сохраняет новое сообщение пользователя и ответ AI в историю диалога.
    Проверяет таймаут и очищает устаревшую историю перед сохранением.
    НЕ сохраняет ошибки AI в историю.
    """
    user_data = get_user(user_id)
    history = user_data.get('conversation_history', [])
    last_message_time = user_data.get('last_message_time')
    
    # Проверяем таймаут - если последнее сообщение было давно, очищаем историю перед сохранением
    if last_message_time:
        try:
            if isinstance(last_message_time, str):
                last_time = datetime.fromisoformat(last_message_time)
            else:
                last_time = last_message_time
            
            if datetime.now() - last_time > timedelta(hours=CONVERSATION_TIMEOUT_HOURS):
                logging.info(f"Очистка устаревшей истории при сохранении для user_id={user_id} (таймаут {CONVERSATION_TIMEOUT_HOURS}ч)")
                history = []  # Очищаем историю перед добавлением нового сообщения
        except Exception as e:
            logging.error(f"Ошибка при проверке таймаута истории при сохранении для user_id={user_id}: {e}")
    
    # Проверяем, не является ли ответ AI ошибкой или пустым (не сохраняем в историю)
    if not ai_response or not ai_response.strip():
        logging.warning(f"НЕ сохраняем пустой ответ AI в историю для user_id={user_id}")
        # Обновляем время последнего сообщения, но НЕ добавляем в историю
        user_data['last_message_time'] = datetime.now()
        save_user_db()
        return
    
    # Проверяем на ТЕХНИЧЕСКИЕ ошибки (не блокируем духовные ответы об ошибках)
    # Технические ошибки имеют специфичные паттерны из core/ai_interaction.py
    is_technical_error = (
        ai_response.startswith("Ошибка:") or  # "Ошибка: API-ключ для DeepSeek не найден"
        ai_response.startswith("Ошибка API:") or  # "Ошибка API: 500 - Internal Server Error"
        ai_response.startswith("Ошибка сети") or  # "Ошибка сети при обращении к AI"
        "при обращении к AI" in ai_response  # "Произошла ошибка при обращении к AI"
    )
    
    if is_technical_error:
        logging.warning(f"НЕ сохраняем техническую ошибку AI в историю для user_id={user_id}: {ai_response[:50]}...")
        # Обновляем время последнего сообщения, но НЕ добавляем в историю
        user_data['last_message_time'] = datetime.now()
        save_user_db()
        return
    
    # Добавляем новые сообщения
    history.append({"role": "user", "content": user_message})
    history.append({"role": "assistant", "content": ai_response})
    
    # Ограничиваем размер истории
    max_messages = MAX_CONVERSATION_HISTORY * 2
    if len(history) > max_messages:
        history = history[-max_messages:]
    
    # Сохраняем обновленную историю и время последнего сообщения
    user_data['conversation_history'] = history
    user_data['last_message_time'] = datetime.now()
    save_user_db()
    
    logging.info(f"Сохранена история диалога для user_id={user_id}, сообщений в истории: {len(history)}")

def clear_conversation_history(user_id: int):
    """
    Очищает историю диалога пользователя (для команды /new_chat).
    """
    user_data = get_user(user_id)
    user_data['conversation_history'] = []
    user_data['last_message_time'] = None
    save_user_db()
    logging.info(f"Очищена история диалога для user_id={user_id}")

# Функция для создания клавиатуры с кнопкой "В избранное"
def get_favorite_keyboard(message_id: int, is_favorited: bool = False) -> InlineKeyboardMarkup:
    text = "⭐️ В избранное" if not is_favorited else "🌟 Удалить из избранного"
    callback_data = f"favorite_{message_id}" if not is_favorited else f"unfavorite_{message_id}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data=callback_data)]
    ])

@router.message(F.text & ~F.text.startswith('/'))
async def handle_text_message(message: Message, bot: Bot, state: FSMContext):
    """
    Этот обработчик будет срабатывать на любое текстовое сообщение, кроме команд.
    Он проверяет, не находится ли пользователь в режиме составления молитвы,
    и в зависимости от этого либо генерирует молитву, либо отвечает как обычно.
    """
    # Пропускаем команды - они должны обрабатываться другими обработчиками
    # Проверяем как обычные команды, так и команды с параметрами
    if message.text:
        text = message.text.strip()
        if text.startswith('/'):
            # Извлекаем имя команды (до пробела или @)
            command_name = text.split()[0].split('@')[0] if ' ' in text or '@' in text else text
            # Явно пропускаем команду /admin
            if command_name == '/admin':
                logging.warning(f"Text handler: BLOCKING /admin command - this should not happen!")
            logging.info(f"Text handler: skipping command {command_name}")
            return
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Проверяем текущее состояние FSM
    current_state = await state.get_state()

    # Сравниваем и по строке (get_state() возвращает строку типа "PrayerState:waiting_for_details")
    is_prayer_state = (
        current_state == PrayerState.waiting_for_details
        or (current_state and str(current_state).startswith("PrayerState"))
    )
    if is_prayer_state:
        user_data = await state.get_data()
        prayer_topic = user_data.get('prayer_topic') or 'молитва'
        user_prayer_details = (message.text or '').strip() or 'о здравии'
        # Убираем кавычки, чтобы не ломать f-строку в промте
        user_prayer_details = user_prayer_details.replace("'", "").replace('"', '')[:500]
        await state.clear()

        logging.info(f"Молитва: user_id={user_id}, тема={prayer_topic}, детали={user_prayer_details[:50]}...")

        async def _typing_loop():
            try:
                while True:
                    await bot.send_chat_action(chat_id, "typing")
                    await asyncio.sleep(4)
            except asyncio.CancelledError:
                pass

        typing_task = asyncio.create_task(_typing_loop())
        ai_response = None
        try:
            prompt = (
                f"Сгенерируй текст православной молитвы в позитивном, вдохновляющем стиле (Норман Пил) на тему '{prayer_topic}' "
                f"с учетом следующей просьбы пользователя: '{user_prayer_details}'. "
                f"Молитва должна быть на современном русском языке, канонически православно корректной и включать обращение, "
                f"прошение, благодарение. Текст до 500 символов, глубокий и добрый."
            )
            ai_response = await get_ai_response(prompt, max_tokens=400)
        except Exception as e:
            logging.exception(f"get_ai_response в модуле Молитва user_id={user_id}: {e}")
            ai_response = None
        finally:
            typing_task.cancel()
            try:
                await typing_task
            except asyncio.CancelledError:
                pass

        if not ai_response or ai_response.startswith("Ошибка") or ai_response.startswith("Произошла ошибка"):
            await message.answer(
                "😔 Извините, произошла ошибка при генерации молитвы. Попробуйте ещё раз: /molitva",
                parse_mode=ParseMode.HTML
            )
            return

        try:
            ai_response = convert_markdown_to_html(ai_response, preserve_html_tags=False)
            header = f"🙏 <b>Ваша молитва ({prayer_topic.lower()})</b>\n\n"
            text_to_send = header + ai_response
            if len(text_to_send) > 1024:
                text_to_send = text_to_send[:1021].rstrip() + "..."

            # Сначала всегда отправляем текстом — гарантированная доставка
            await message.answer(
                text_to_send,
                parse_mode=ParseMode.HTML,
                reply_markup=get_favorite_keyboard(message.message_id)
            )
        except Exception as e:
            logging.exception(f"Отправка молитвы user_id={user_id}: {e}")
            try:
                await message.answer(
                    "🙏 <b>Ваша молитва</b>\n\n" + ai_response[:4000],
                    parse_mode=ParseMode.HTML
                )
            except Exception:
                await message.answer(
                    "😔 Не удалось отправить молитву. Попробуйте ещё раз: /molitva",
                    parse_mode=ParseMode.HTML
                )
        return

    # Календарь запрашивается отдельной командой /calendar

    # Если не в режиме молитвы и не запрос календаря, работаем как обычно
    # Получаем историю диалога для контекста
    conversation_history = get_conversation_history(user_id)
    
    # Получаем имя пользователя для персонализации
    user_name = message.from_user.first_name if message.from_user.first_name else None
    
    # Отправляем запрос к AI с контекстом истории и именем
    ai_response = await get_ai_response(
        message.text, 
        conversation_history=conversation_history,
        user_name=user_name
    )
    
    # Сохраняем сообщение пользователя и ответ AI в историю
    save_conversation_history(user_id, message.text, ai_response)
    
    # Преобразуем Markdown в HTML (без сохранения HTML-тегов для безопасности)
    ai_response = convert_markdown_to_html(ai_response, preserve_html_tags=False)
    formatted_response = ai_response.replace('\n', '\n\n') # Возможно, это уже не нужно, если convert_markdown_to_html обрабатывает \n
    await send_and_delete_previous(
        bot=bot,
        chat_id=chat_id,
        state=state,
        text=formatted_response,
        reply_markup=get_favorite_keyboard(message.message_id),
        delete_previous=False,
        track_last_message=False
    )

@router.callback_query(F.data.startswith('favorite_'))
async def handle_favorite_callback(callback_query: CallbackQuery, bot: Bot, state: FSMContext):
    original_message_id = int(callback_query.data.split('_')[1])
    user_id = callback_query.from_user.id
    chat_id = callback_query.message.chat.id

    # Получаем сообщение, которое пользователь хочет добавить в избранное
    # Это сообщение, на которое была нажата кнопка "В избранное"
    bot_message = callback_query.message
    
    # Извлекаем контент и имя изображения
    content = bot_message.html_text
    image_name = None
    # TODO: Реализовать сохранение image_name для избранного
    # Для этого нужно будет сохранять image_name в FSMContext при отправке сообщения
    # и извлекать его здесь. Пока оставляем None.

    if add_favorite_message(user_id, bot_message.message_id, original_message_id, content, image_name):
        await callback_query.answer("Сообщение добавлено в избранное! 🌟")
        # Обновляем кнопку, чтобы показать, что сообщение уже в избранном
        await bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=bot_message.message_id,
            reply_markup=get_favorite_keyboard(original_message_id, is_favorited=True)
        )
    else:
        await callback_query.answer("Не удалось добавить сообщение в избранное.", show_alert=True)

@router.callback_query(F.data.startswith('unfavorite_'))
async def handle_unfavorite_callback(callback_query: CallbackQuery, bot: Bot, state: FSMContext):
    original_message_id = int(callback_query.data.split('_')[1])
    user_id = callback_query.from_user.id
    chat_id = callback_query.message.chat.id
    bot_message_id = callback_query.message.message_id

    if remove_favorite_message(user_id, bot_message_id):
        await callback_query.answer("Сообщение удалено из избранного. 🗑️")
        # Обновляем кнопку, чтобы показать, что сообщение больше не в избранном
        await bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=bot_message_id,
            reply_markup=get_favorite_keyboard(original_message_id, is_favorited=False)
        )
    else:
        await callback_query.answer("Не удалось удалить сообщение из избранного.", show_alert=True)
