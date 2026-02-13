import logging
import os
from aiogram import Bot
from aiogram.types import FSInputFile, InlineKeyboardMarkup, Message
from aiogram.enums import ParseMode, ChatAction
from aiogram.fsm.context import FSMContext
from utils.html_parser import convert_markdown_to_html

async def send_content_message(bot: Bot, chat_id: int, text: str, image_name: str = None, reply_markup: InlineKeyboardMarkup = None) -> Message | None:
    """
    Отправляет сообщение с изображением (опционально), подписью и опциональной инлайн-клавиатурой.

    :param bot: Экземпляр бота Aiogram.
    :param chat_id: ID чата для отправки.
    :param text: Текст сообщения (будет использован как подпись).
    :param image_name: Имя файла изображения в 'assets/images/'.
    :param reply_markup: Инлайн-клавиатура для сообщения.
    :return: Отправленное сообщение или None в случае ошибки.
    """
    html_text = convert_markdown_to_html(text)
    
    # Не используем изображения с pravoslavie.ru (риск претензий по авторским правам)
    if image_name and ('pravoslavie.ru' in image_name or 'days.pravoslavie' in image_name):
        logging.info(f"Пропуск изображения с pravoslavie.ru: {image_name[:80]}...")
        image_name = None
    
    try:
        if image_name:
            # Проверяем, является ли image_name URL
            if image_name.startswith('http://') or image_name.startswith('https://'):
                sent_message = await bot.send_photo(
                    chat_id=chat_id,
                    photo=image_name, # Передаем URL напрямую
                    caption=html_text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup
                )
            else:
                # Если это не URL, то это локальный путь к файлу
                photo_path = os.path.join('assets', 'images', image_name)
                if os.path.exists(photo_path):
                    photo = FSInputFile(photo_path)
                    sent_message = await bot.send_photo(
                        chat_id=chat_id,
                        photo=photo,
                        caption=html_text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=reply_markup
                    )
                else:
                    logging.warning(f"Изображение не найдено локально: {photo_path}. Отправляем только текст.")
                    sent_message = await bot.send_message(
                        chat_id=chat_id,
                        text=html_text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=reply_markup
                    )
        else:
            sent_message = await bot.send_message(
                chat_id=chat_id,
                text=html_text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
        return sent_message
    except Exception as e:
        logging.error(f"Ошибка при отправке сообщения в чат {chat_id}: {e}")
        return None

async def send_and_delete_previous(
    bot: Bot, 
    chat_id: int, 
    state: FSMContext, 
    text: str, 
    image_name: str = None, 
    reply_markup: InlineKeyboardMarkup = None,
    show_typing: bool = True,
    delete_previous: bool = True,
    track_last_message: bool = True
) -> Message | None:
    """
    Отправляет сообщение, предварительно удаляя предыдущее сообщение бота,
    сохраненное в FSMContext, и сохраняет message_id нового сообщения.
    Также может показывать статус "печатает".

    :param bot: Экземпляр бота Aiogram.
    :param chat_id: ID чата для отправки.
    :param state: FSMContext пользователя.
    :param text: Текст сообщения.
    :param image_name: Имя файла изображения (опционально).
    :param reply_markup: Инлайн-клавиатура (опционально).
    :param show_typing: Показывать ли статус "печатает" перед отправкой.
    :param track_last_message: Сохранять ли message_id для последующего удаления.
    :return: Отправленное сообщение или None.
    """
    if show_typing:
        await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    if delete_previous:
        user_data = await state.get_data()
        last_bot_message_id = user_data.get('last_bot_message_id')

        if last_bot_message_id:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=last_bot_message_id)
                logging.info(f"Удалено предыдущее сообщение бота {last_bot_message_id} в чате {chat_id}")
            except Exception as e:
                logging.warning(f"Не удалось удалить предыдущее сообщение бота {last_bot_message_id} в чате {chat_id}: {e}")

    sent_message = await send_content_message(
        bot=bot,
        chat_id=chat_id,
        text=text,
        image_name=image_name,
        reply_markup=reply_markup
    )

    if sent_message and track_last_message:
        await state.update_data(last_bot_message_id=sent_message.message_id)
    
    return sent_message
