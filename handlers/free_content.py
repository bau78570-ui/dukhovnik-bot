import locale
import os
import re # Добавляем импорт re для регулярных выражений
from datetime import datetime, timedelta
from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ChatAction
from aiogram.fsm.context import FSMContext # Импортируем FSMContext
from core.content_sender import send_and_delete_previous, send_content_message # Импортируем новую централизованную функцию
from core.calendar_data import get_calendar_data, fetch_and_cache_calendar_data

# Устанавливаем русскую локаль для корректного отображения месяца
try:
    locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')
except locale.Error:
    pass

# Создаем роутер для обработчиков бесплатного контента
router = Router()

@router.message(Command("calendar"))
async def calendar_handler(message: Message, bot: Bot, state: FSMContext):
    """
    Обработчик для команды /calendar.
    Получает данные о текущем дне с pravoslavie.ru и azbyka.ru и отправляет пользователю.
    """
    chat_id = message.chat.id
    await bot.send_chat_action(chat_id, ChatAction.UPLOAD_PHOTO)

    try:
        target_date = datetime.now()
        date_str = target_date.strftime("%Y%m%d")
        calendar_data = await fetch_and_cache_calendar_data(date_str) or {} # Убедимся, что calendar_data всегда является словарем

        if not calendar_data: # Если calendar_data все еще пуст после установки значения по умолчанию
            print(f"ERROR: calendar_data is empty for date {date_str}")
            await send_and_delete_previous(
                bot=bot,
                chat_id=chat_id,
                state=state,
                text="Простите, не удалось получить актуальные данные календаря.",
                show_typing=False
            )
            return

        # Формируем список праздников
        holidays_text = ""
        holidays = calendar_data.get("holidays", [])
        if holidays:
            holidays_text = "✨ <b>Праздники:</b>\n" + "\n".join([f"• {h}" for h in holidays]) + "\n\n"
        else:
            holidays_text = "✨ <b>Сегодня больших праздников не найдено.</b>\n\n"
        
        # Формируем список именин
        namedays_text = ""
        namedays = calendar_data.get("namedays", [])
        if namedays:
            namedays_text = "😇 <b>Именины:</b>\n" + "\n".join([f"• {n}" for n in namedays]) + "\n\n"
        else:
            namedays_text = "😇 <b>Именин нет.</b>\n\n"

        # Основная часть сообщения
        main_caption_text = (
            f"🗓️ <b>Православный календарь на сегодня</b> ✨\n\n"
            f"🗓️ <b>Дата:</b> {target_date.strftime('%d.%m.%Y')}\n\n"
            f"{holidays_text}"
            f"ℹ️ <b>Пост:</b> {calendar_data.get('fasting', 'Информация о посте не найдена.')}\n\n"
            f"🏛️ <b>Седмица:</b> {calendar_data.get('week_info', 'Информация о седмице не найдена.')}\n\n"
            f"{namedays_text}" +
            f"_Данные предоставлены pravoslavie.ru и azbyka.ru_"
        )

        builder = InlineKeyboardBuilder()
        
        # Отправляем сообщение с изображением, если оно есть
        image_url = calendar_data.get("image_url")
        if image_url:
            await send_and_delete_previous(
                bot=bot,
                chat_id=chat_id,
                state=state,
                text=main_caption_text,
                image_name=image_url, # Предполагаем, что image_url здесь - это относительный путь к файлу
                reply_markup=builder.as_markup(),
                show_typing=False,
                delete_previous=False # Не удаляем предыдущее сообщение (команду пользователя)
            )
        else:
            await send_and_delete_previous(
                bot=bot,
                chat_id=chat_id,
                state=state,
                text=main_caption_text,
                reply_markup=builder.as_markup(),
                show_typing=False,
                delete_previous=False # Не удаляем предыдущее сообщение (команду пользователя)
            )

        # Отдельное сообщение для мыслей Феофана Затворника, если они есть
        theophan_thoughts = calendar_data.get('theophan_thoughts', [])
        if theophan_thoughts:
            header = "📖 <b>Мысли Святителя Феофана Затворника на каждый день года:</b>\n\n"
            
            formatted_thoughts = []
            for thought in theophan_thoughts:
                cleaned_thought = re.sub(r'^\s*[\(\);,.]+\s*', '', thought) # Удаляем начальные символы из каждого абзаца
                if cleaned_thought.strip():
                    formatted_thoughts.append(f"✨ <i>{cleaned_thought.strip()}</i>\n\n")
            
            theophan_message_text = header + "".join(formatted_thoughts).strip()
            await send_and_delete_previous(
                bot=bot,
                chat_id=chat_id,
                state=state,
                text=theophan_message_text,
                show_typing=False,
                delete_previous=False # Не удаляем предыдущее сообщение (основной календарь)
            )
        else:
            await send_and_delete_previous(
                bot=bot,
                chat_id=chat_id,
                state=state,
                text="📖 <b>Мысли Святителя Феофана Затворника на каждый день года:</b>\nНет мыслей на этот день.",
                show_typing=False,
                delete_previous=False # Не удаляем предыдущее сообщение (основной календарь)
            )

    except Exception as e:
        print(f"ERROR: Непредвиденная ошибка в calendar_handler: {e}")
        await send_and_delete_previous(
            bot=bot,
            chat_id=chat_id,
            state=state,
            text="Простите, произошла непредвиденная ошибка при загрузке календаря. Пожалуйста, попробуйте чуть позже.",
            show_typing=False
        )


@router.message(Command("molitva"))
async def molitva_handler(message: Message, bot: Bot, state: FSMContext):
    """
    Обработчик для команды /molitva.
    Предлагает пользователю составить молитву.
    """
    text = (
        "🙏 <b>Молитва</b>\n\n"
        "Молитва — это искренний разговор с Богом. "
        "Я могу помочь тебе облечь твои чувства в слова. "
        "Напиши мне о чем или о ком ты хотел бы помолиться сегодня?"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="О здоровье", callback_data="prayer_topic:health")
    builder.button(text="В делах", callback_data="prayer_topic:work")
    builder.button(text="О семье", callback_data="prayer_topic:family")
    builder.button(text="Своими словами", callback_data="prayer_topic:custom")
    builder.adjust(2)

    sent_message = await send_content_message(
        bot=bot,
        chat_id=message.chat.id,
        text=text,
        image_name='daily_quote.png',
        reply_markup=builder.as_markup()
    )
    if sent_message:
        await state.update_data(last_bot_message_id=sent_message.message_id)

@router.message(Command("subscribe"))
async def subscribe_handler(message: Message, bot: Bot, state: FSMContext):
    """
    Обработчик для команды /subscribe.
    Отправляет предложение о подписке.
    """
    # Создаем инлайн-кнопку с ссылкой на оплату
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Оформить подписку за 290 руб/мес",
        url="https://paywall.tg"  # TODO: Заменить на реальную ссылку
    )

    # Формируем текст
    subscribe_text = (
        "✨ <b>Откройте мир глубокого духовного роста с Premium-подпиской «Духовник»!</b> ✨\n\n"
        "С Premium-доступом вы получаете личного проводника на пути к гармонии и душевному покою.\n\n"
        "<b>Что вас ждет:</b>\n"
        "💬 <b>Безграничные диалоги с AI-Собеседником:</b> Мудрые ответы на вопросы о вере в любое время.\n"
        "📖 <b>Ежедневное «Слово Дня» с AI-размышлением:</b> Вдохновляющие отрывки из Библии и персонализированные размышления.\n"
        "🙏 <b>Помощь в составлении молитв:</b> Сформулируйте искреннюю молитву о здоровье, семье, делах или по любому поводу.\n"
        "🗓️ <b>Расширенный Православный Календарь:</b> Все праздники, посты, именины и глубокие мысли Святителя Феофана Затворника.\n"
        "⚙️ <b>Персонализированные уведомления:</b> Настройте получение утреннего вдохновения и вечерних размышлений.\n\n"
        "<b>Это инвестиция в ваш внутренний мир, спокойствие и уверенность.</b> Позвольте себе жить полной духовной жизнью!\n\n"
        "<b>Не упустите возможность преобразить свою жизнь!</b> 👇 Нажмите кнопку ниже и начните свой путь к глубокой вере и гармонии уже сегодня!"
    )
    
    # Отправляем фото с подписью и кнопкой
    await send_and_delete_previous(
        bot=bot,
        chat_id=message.chat.id,
        state=state,
        text=subscribe_text,
        image_name='logo.png',
        reply_markup=builder.as_markup(),
        show_typing=False
    )




@router.message(Command("daily_word"))
async def daily_word_handler(message: Message, bot: Bot, state: FSMContext):
    """
    Обработчик для команды /daily_word.
    Заглушка для Слова Дня.
    """
    await send_and_delete_previous(
        bot=bot,
        chat_id=message.chat.id,
        state=state,
        text="Готовлю Слово Дня...",
        show_typing=False
    )
