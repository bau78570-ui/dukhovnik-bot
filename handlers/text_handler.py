from aiogram import Router, F, Bot
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext # Импортируем FSMContext
from core.ai_interaction import get_ai_response
from states import PrayerState # Импортируем состояния
from core.calendar_data import get_calendar_data
import logging # Импортируем logging
from datetime import datetime
import os # Импортируем os для работы с путями файлов
import random # Импортируем random для выбора случайного изображения
from core.content_sender import send_and_delete_previous # Импортируем новую централизованную функцию
from utils.html_parser import convert_markdown_to_html # Импортируем convert_markdown_to_html
from core.user_database import add_favorite_message, get_favorite_messages, remove_favorite_message # Импортируем функции для избранного

# Создаем роутер для этого обработчика
router = Router()

# Функция для создания клавиатуры с кнопкой "В избранное"
def get_favorite_keyboard(message_id: int, is_favorited: bool = False) -> InlineKeyboardMarkup:
    text = "⭐️ В избранное" if not is_favorited else "🌟 Удалить из избранного"
    callback_data = f"favorite_{message_id}" if not is_favorited else f"unfavorite_{message_id}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data=callback_data)]
    ])

@router.message(F.text)
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

    if current_state == PrayerState.waiting_for_details:
        # Если пользователь в режиме ожидания деталей молитвы
        user_data = await state.get_data()
        prayer_topic = user_data.get('prayer_topic')
        user_prayer_details = message.text

        # Формируем специальный промт для get_ai_response
        prompt = (
            f"Сгенерируй текст православной молитвы в позитивном, вдохновляющем стиле (Норман Пил) на тему '{prayer_topic}' "
            f"с учетом следующей просьбы пользователя: '{user_prayer_details}'. "
            f"Молитва должна быть на современном русском языке, канонически православно корректной и включать обращение, "
            f"прошение, благодарение. Текст должен быть объемным (до 500 символов), глубоким, добрым и человечным. "
            f"Должно оставаться ощущение будто молитва написана батюшкой из руской православной церкви."
        )
        
        # Получаем ответ от AI
        ai_response = await get_ai_response(prompt)
        
        # Сбрасываем состояние пользователя
        await state.clear()
        
        # Преобразуем Markdown в HTML
        ai_response = convert_markdown_to_html(ai_response)
        
        # Выбираем случайное изображение из assets/images/daily_word/ для рассылки
        daily_word_images_path = 'assets/images/daily_word/'
        fallback_image_name = 'logo.png' # Запасное изображение
        image_to_send_name = fallback_image_name
        try:
            if os.path.exists(daily_word_images_path) and os.listdir(daily_word_images_path):
                image_files = [f for f in os.listdir(daily_word_images_path) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
                if image_files:
                    random_image = random.choice(image_files)
                    image_to_send_name = os.path.join('daily_word', random_image) # Путь относительно assets/images/
                    logging.info(f"Выбрано изображение для молитвы: {image_to_send_name}")
                else:
                    logging.warning(f"WARNING: В папке {daily_word_images_path} нет подходящих изображений для молитвы. Используется запасное.")
            else:
                os.makedirs(daily_word_images_path, exist_ok=True)
                logging.warning(f"WARNING: Папка {daily_word_images_path} не найдена или пуста для молитвы. Используется запасное изображение.")
        except Exception as e:
            logging.error(f"ERROR: Ошибка при выборе изображения для молитвы: {e}. Используется запасное.")

        # Обрезаем scripture, если он слишком длинный (хотя в этом хендлере scripture не используется напрямую в final_text,
        # но это может быть полезно для будущих изменений или если AI-ответ будет включать scripture)
        # В данном случае, scripture используется в промте, но не в конечном formatted_response.
        # Однако, для единообразия и предотвращения потенциальных проблем с длиной,
        # можно было бы обрезать и здесь, если бы scripture напрямую вставлялся в formatted_response.
        # Поскольку formatted_response состоит из заголовка и ai_response, и ai_response уже ограничен до 200 символов,
        # то проблема длины подписи, скорее всего, не в этом месте.
        # Проблема, вероятно, в том, что AI-ответ все еще слишком длинный, несмотря на ограничение в промте.
        # Уменьшим ограничение для AI-ответа еще сильнее.

        # Добавляем заголовок к сгенерированной молитве
        formatted_response = f"🙏 <b>Ваша молитва ({prayer_topic.lower()})</b>\n\n{ai_response}"
        
        # Отправляем сообщение с изображением, используя новую централизованную функцию
        await send_and_delete_previous(
            bot=bot,
            chat_id=chat_id,
            state=state,
            text=formatted_response,
            image_name=image_to_send_name,
            reply_markup=get_favorite_keyboard(message.message_id) # Добавляем кнопку "В избранное"
        )
        return # Прекращаем дальнейшую обработку этого сообщения

    # Календарь запрашивается отдельной командой /calendar

    # Если не в режиме молитвы и не запрос календаря, работаем как обычно
    ai_response = await get_ai_response(message.text)
    # Преобразуем Markdown в HTML
    ai_response = convert_markdown_to_html(ai_response)
    formatted_response = ai_response.replace('\n', '\n\n') # Возможно, это уже не нужно, если convert_markdown_to_html обрабатывает \n
    await send_and_delete_previous(
        bot=bot,
        chat_id=chat_id,
        state=state,
        text=formatted_response,
        reply_markup=get_favorite_keyboard(message.message_id)
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
