from aiogram import F, Router, Bot
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, FSInputFile, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext # Импортируем FSMContext
from core.content_sender import send_and_delete_previous, send_content_message # Импортируем новую централизованную функцию
from core.user_database import get_user # Импортируем get_user
from core.subscription_checker import is_premium # Импортируем is_premium
import logging # Импортируем logging

# Создаем роутер для этого обработчика
router = Router()

@router.message(CommandStart())
async def command_start_handler(message: Message, bot: Bot, state: FSMContext) -> None:
    """
    Этот обработчик будет срабатывать на команду /start
    """
    chat_id = message.chat.id
    
    # Сначала убираем старую клавиатуру (сброс кэша Telegram)
    await message.answer("♻️", reply_markup=ReplyKeyboardRemove())
    
    # 1. Отправка изображения с приветственной подписью
    welcome_caption = (
        "🕊️ Мир вам! Я — <b>Духовник</b>, ваш цифровой собеседник в вопросах веры. "
        "Я здесь, чтобы помочь и поддержать вас в духовном поиске."
    )
    await send_content_message(
        bot=bot,
        chat_id=chat_id,
        text=welcome_caption,
        image_name='onboarding.png'
    )

    # 2. Отправка дисклеймера и кнопок
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Начать 3 дня бесплатно", callback_data="start_trial")
    builder.button(text="📄 Условия использования", callback_data="show_terms")
    builder.adjust(2)

    disclaimer_text = (
        "<i>Важно: Я — нейросеть, а не священник. Мои ответы основаны на православных учениях и текстах, "
        "но не являются каноническими указаниями и не заменяют Таинств Церкви и живого общения с духовником. "
        "Проект является частной инициативой и не связан с РПЦ.</i>"
    )
    trial_text = "Вы можете начать наш разговор прямо сейчас. Вам доступен бесплатный пробный период на 3 дня с полным функционалом."

    info_text = f"{disclaimer_text}\n\n{trial_text}"

    await message.answer(
        text=info_text,
        reply_markup=builder.as_markup(),
        parse_mode='HTML'
    )



@router.callback_query(F.data == "start_trial")
async def start_trial_handler(query: CallbackQuery, bot: Bot, state: FSMContext):
    """
    Этот обработчик будет срабатывать на нажатие инлайн-кнопки
    с callback_data="start_trial" и активировать пробный период.
    """
    user_id = query.from_user.id
    from core.subscription_checker import activate_trial, TRIAL_DURATION_DAYS # Импортируем здесь, чтобы избежать циклического импорта

    if await activate_trial(user_id):
        await query.message.edit_text(
            text=f"🎉 <b>Поздравляем!</b> Ваш бесплатный пробный период на {TRIAL_DURATION_DAYS} дня активирован.\n"
                 "Теперь вы можете пользоваться всеми функциями бота без ограничений!",
            parse_mode='HTML'
        )
    else:
        await query.message.edit_text(
            text="Вы уже активировали пробный период ранее или он истек. "
                 "Для продолжения использования Premium-функций, пожалуйста, оформите подписку: /subscribe",
            parse_mode='HTML'
        )
    await query.answer()
