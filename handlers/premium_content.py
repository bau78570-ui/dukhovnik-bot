# -*- coding: utf-8 -*-
import random
import os
import re
from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardButton, CallbackQuery, InputMediaPhoto
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import FSInputFile # Добавляем импорт FSInputFile
from aiogram.fsm.context import FSMContext # Импортируем FSMContext
import logging # Импортируем logging
from core.content_sender import send_and_delete_previous, send_content_message # Импортируем новую централизованную функцию
from core.subscription_checker import check_access
from core.content_library import daily_words # Импортируем daily_words
from core.ai_interaction import get_ai_response # Импортируем функцию для AI-генерации
from utils.html_parser import convert_markdown_to_html # Импортируем для преобразования markdown в HTML
# from handlers.callbacks import prayer_topic_handler # Этот импорт больше не нужен, так как мы не вызываем хендлер напрямую

# Создаем роутер для премиум-обработчиков
router = Router()
# Применяем middleware для проверки доступа ко всем хэндлерам в этом роутере
router.message.middleware(check_access)
router.callback_query.middleware(check_access)

# @router.message(Command("daily_quote"))
# async def daily_quote_handler(message: Message, bot: Bot):
#     """
#     Обработчик для команды /daily_quote.
#     Отправляет случайную цитату с изображением.
#     """
#     # Выбираем случайную цитату
#     random_quote = random.choice(daily_quotes)
#     quote_text = random_quote['quote']
#     author = random_quote['author']

#     # Форматируем текст
#     text = f"✨ <b>Цитата дня:</b>\n\n<i>«{quote_text}»</i>\n\n<b>— {author}</b>"
#     image_name = 'daily_quote.png'
#     await send_content_message(bot, message.chat.id, text, image_name)

@router.message(Command("daily_word"))
async def daily_word_command_handler(message: Message, bot: Bot, state: FSMContext):
    """
    Обработчик для команды /daily_word.
    Отправляет интерактивное сообщение для получения "Слова Дня".
    """
    text = ("📖 <b>Слово Дня</b>\n\n"
            "Получите вдохновляющий отрывок из Библии, который поможет вам начать день с верой и размышлением.")
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Получить Слово Дня", callback_data="get_daily_word"))
    
    # Используем 'logo.png' как изображение по умолчанию для этой команды
    sent_message = await send_content_message(
        bot=bot,
        chat_id=message.chat.id,
        text=text,
        image_name='logo.png',
        reply_markup=builder.as_markup()
    )
    if sent_message:
        await state.update_data(last_bot_message_id=sent_message.message_id)


@router.callback_query(F.data == "get_daily_word")
async def get_daily_word_callback_handler(callback: CallbackQuery, bot: Bot, state: FSMContext):
    """
    Обрабатывает нажатие на кнопку "Получить Слово Дня" и генерирует размышление.
    """
    await callback.answer("Генерирую Слово Дня...", show_alert=False)
    chat_id = callback.message.chat.id
    
    # Удаляем предыдущее сообщение с кнопкой "Получить Слово Дня" (закомментировано, так как теперь мы редактируем)
    # try:
    #     await bot.delete_message(chat_id=chat_id, message_id=callback.message.message_id)
    # except Exception as e:
    #     logging.warning(f"Не удалось удалить сообщение с кнопкой 'Получить Слово Дня': {e}")

    try:
        # Проверка на наличие daily_words
        if not daily_words:
            logging.error("ERROR: daily_words библиотека пуста в get_daily_word_callback_handler.")
            await callback.message.answer("Простите, библиотека 'Слово Дня' пуста. Пожалуйста, попробуйте позже.")
            await callback.answer()
            return

        # Выбираем случайный элемент из daily_words
        selected_word = random.choice(daily_words)
        scripture = selected_word['scripture']
        source = selected_word['source']
        logging.info(f"Слово Дня: {scripture} — {source}")

        # Формируем промт для AI
        prompt = (
            f"На основе стиха _{scripture}_, "
            "напиши очень краткое (1 абзац, до 150 символов) вдохновляющее размышление в позитивном стиле "
            "(Норман Пил, православный контекст). Сделай акцент на практическом применении "
            "этой мысли в сегодняшнем дне."
        )
        logging.info(f"Сформирован промт для AI: {prompt[:100]}...") # Логируем часть промта
        
        # Получаем AI-ответ
        ai_reflection = await get_ai_response(prompt)
        if not ai_reflection:
            logging.error("ERROR: AI-ответ для Слова Дня пуст.")
            await callback.message.answer("Простите, не удалось получить размышление от AI. Пожалуйста, попробуйте позже.")
            await callback.answer()
            return
        logging.info("Получен AI-ответ для Слова Дня.")

        # Преобразуем markdown в HTML для ai_reflection
        ai_reflection_html = convert_markdown_to_html(ai_reflection)

        # Обрезаем scripture, если он слишком длинный
        max_scripture_len = 200
        display_scripture = scripture
        if len(scripture) > max_scripture_len:
            display_scripture = scripture[:max_scripture_len].rsplit(' ', 1)[0] + "..." # Обрезаем по слову

        # Подготавливаем финальный текст с источником
        source_text = f"\n\nИсточник: {source}"
        final_text_without_ai = (
            f"📖 <b>Слово Дня</b>\n\n"
            f"<b>{display_scripture}</b>\n\n"
        )
        
        # Проверяем общую длину текста (без HTML-тегов) и обрезаем ai_reflection при необходимости
        max_total_length = 350
        # Оцениваем длину текста без HTML-тегов для проверки ограничения
        text_without_html_length = len(re.sub(r'<[^>]+>', '', final_text_without_ai + source_text))
        available_length = max_total_length - text_without_html_length
        
        # Обрезаем ai_reflection, если нужно (оставляем запас, так как HTML может добавить длину)
        if len(ai_reflection) > available_length - 50:
            # Учитываем длину суффикса "..." (3 символа) при обрезке
            max_reflection_length = available_length - 50 - 3
            truncated = ai_reflection[:max_reflection_length]
            # Пытаемся обрезать по последнему пробелу, если он есть
            if ' ' in truncated:
                ai_reflection = truncated.rsplit(' ', 1)[0] + "..."
            else:
                # Если пробелов нет, обрезаем напрямую и добавляем "..."
                ai_reflection = truncated + "..."
            ai_reflection_html = convert_markdown_to_html(ai_reflection)
        
        # Формируем финальный текст
        final_text = final_text_without_ai + ai_reflection_html + source_text

        # Выбираем случайное изображение из assets/images/daily_word/
        image_dir = 'daily_word' # Относительный путь внутри assets/images/
        fallback_image_name = 'logo.png' # Запасное изображение, которое точно существует
        
        final_image_name = fallback_image_name # Инициализируем запасным

        full_image_dir_path = os.path.join('assets', 'images', image_dir)
        if os.path.exists(full_image_dir_path):
            image_files = [f for f in os.listdir(full_image_dir_path) if f.endswith(('.png', '.jpg', '.jpeg'))]
            if image_files:
                selected_image_file = random.choice(image_files)
                final_image_name = os.path.join(image_dir, selected_image_file) # Путь относительно assets/images/
                logging.info(f"Выбрано изображение: {final_image_name}")
            else:
                logging.warning(f"WARNING: В папке {full_image_dir_path} нет подходящих изображений. Используется запасное: {fallback_image_name}.")
        else:
            logging.warning(f"WARNING: Папка {full_image_dir_path} не существует. Используется запасное изображение: {fallback_image_name}.")

        # Создаем инлайн-кнопку "Помолиться об этом"
        builder = InlineKeyboardBuilder()
        # Изменяем callback_data, чтобы он соответствовал формату prayer_topic:
        builder.row(InlineKeyboardButton(text="🙏 Помолиться об этом", callback_data=f"prayer_topic:daily_word_reflection"))
        
        # Отправляем сообщение
        try:
            # Редактируем существующее сообщение
            await callback.message.edit_media(
                media=InputMediaPhoto(media=FSInputFile(os.path.join('assets', 'images', final_image_name)), caption=final_text, parse_mode='HTML'),
                reply_markup=builder.as_markup()
            )
            logging.info("Слово Дня успешно отредактировано пользователю.")
        except Exception as send_e:
            logging.error(f"ERROR: Ошибка при редактировании Слова Дня пользователю: {send_e}")
            await callback.message.answer(
                text="Простите, произошла ошибка при отправке Слова Дня. Пожалуйста, попробуйте позже.",
                parse_mode='HTML'
            )
            await callback.answer()
            return
        
    except Exception as e:
        logging.error(f"ERROR: Непредвиденная ошибка в get_daily_word_callback_handler: {e}")
        await callback.message.answer(
            text="Простите, произошла ошибка при получении Слова Дня. Пожалуйста, попробуйте позже.",
            parse_mode='HTML'
        )
        await callback.answer()


# @router.message(Command("fasting_info"))
# async def fasting_info_handler(message: Message, bot: Bot):
#     """
#     Обработчик для команды /fasting_info.
#     Отправляет информацию о посте с кнопками для рецепта и мысли дня.
#     """
#     text = ("🌿 <b>Время поста</b>\n\n"
#             "Пост — это не только воздержание в пище, но и время для духовного роста, молитвы и добрых дел. "
#             "Мы подготовили для вас полезные материалы, чтобы поддержать вас на этом пути.")
#     image_name = 'fasting_post.png'

#     # Создаем инлайн-клавиатуру
#     builder = InlineKeyboardBuilder()
#     builder.row(InlineKeyboardButton(text="🍽️ Постный рецепт дня", callback_data="fasting_recipe_of_the_day"))
#     builder.row(InlineKeyboardButton(text="💡 Мысль на время поста", callback_data="fasting_thought_of_the_day"))

#     await send_content_message(bot, message.chat.id, text, image_name, reply_markup=builder.as_markup())
