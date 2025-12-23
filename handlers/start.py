from aiogram import F, Router, Bot
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, FSInputFile, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext # Импортируем FSMContext
from datetime import datetime # Импортируем datetime
from core.content_sender import send_and_delete_previous, send_content_message # Импортируем новую централизованную функцию
from core.user_database import get_user, user_db # Импортируем get_user и user_db
from core.subscription_checker import is_premium # Импортируем is_premium
import logging # Импортируем logging

# Создаем роутер для этого обработчика
router = Router()

@router.message(CommandStart())
async def command_start_handler(message: Message, bot: Bot, state: FSMContext) -> None:
    """
    Этот обработчик будет срабатывать на команду /start
    """
    # Регистрируем пользователя в базе данных
    user_id = message.from_user.id
    
    # Если пользователя нет в базе, создаем запись с пробным периодом
    if user_id not in user_db:
        user_db[user_id] = {
            'subscription_status': 'free',
            'trial_start_date': datetime.now(),
            'notifications': {'morning': True, 'daily': True, 'evening': True},
            'prayer_mode_topic': None,
            'nameday_persons': [],
            'favorites': []
        }
        logging.info(f"Новый пользователь добавлен: {user_id}")
    else:
        get_user(user_id)  # Создает запись пользователя, если его еще нет
    
    # Проверяем pending платежи при возврате пользователя (например, после оплаты на сайте ЮKassa)
    # Используем ленивый импорт, чтобы избежать циклического импорта
    user_data = get_user(user_id)
    pending_payments = user_data.get('pending_payments', {})
    if pending_payments:
        logging.info(f"Обнаружены pending платежи для user_id={user_id}, проверяем статус...")
        # Импортируем функцию внутри обработчика, чтобы избежать циклического импорта
        from handlers.payment_handler import check_and_activate_payment
        activated = False
        for payment_id, payment_info in list(pending_payments.items()):
            if payment_info.get('status') == 'pending':
                try:
                    if await check_and_activate_payment(user_id, payment_id):
                        activated = True
                        logging.info(f"Premium подписка автоматически активирована для user_id={user_id} после оплаты payment_id={payment_id}")
                except Exception as e:
                    logging.error(f"Ошибка при автоматической проверке платежа {payment_id} для user_id={user_id}: {e}", exc_info=True)
        
        if activated:
            # Отправляем уведомление об активации Premium
            await message.answer(
                "✨ <b>Отлично! Premium подписка активирована!</b> ✨\n\n"
                "Ваша Premium подписка на 30 дней успешно активирована.\n\n"
                "Теперь у вас есть доступ ко всем Premium функциям:\n"
                "💬 Безграничные диалоги с AI-Собеседником\n"
                "📖 Ежедневное «Слово Дня» с AI-размышлением\n"
                "🙏 Помощь в составлении молитв\n"
                "🗓️ Расширенный Православный Календарь\n"
                "⚙️ Персонализированные уведомления\n\n"
                "Желаем вам духовного роста и гармонии! 🙏",
                parse_mode='HTML'
            )
    
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
    builder.button(text="📄 Условия использования", url="https://teletype.in/@doc_content/IWP-06AxhyO")
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
