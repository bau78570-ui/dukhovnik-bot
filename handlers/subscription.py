import os
import logging
from datetime import datetime, timedelta
from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.types import Message, PreCheckoutQuery, LabeledPrice, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from dotenv import load_dotenv
from core.user_database import user_db, get_user, save_user_db
from core.subscription_checker import activate_premium_subscription, activate_trial

load_dotenv()

# Получаем токены из .env
# ВАЖНО: PROVIDER_TOKEN - это токен для Telegram Payments, который выдается через @BotFather
# после подключения вашего бота к боту ЮKassa.
# 
# Инструкция по получению токена (согласно https://yookassa.ru/docs/support/payments/onboarding/integration/cms-module/telegram):
# 1. Откройте @BotFather в Telegram
# 2. Выполните команду /mybots
# 3. Выберите вашего бота
# 4. Выберите "Payments"
# 5. Выберите "Connect ЮKassa: тест" (для теста) или "Connect ЮKassa: платежи" (для продакшена)
# 6. Авторизуйтесь в ЮKassa и разрешите доступ
# 7. @BotFather покажет вам токен - это и есть PROVIDER_TOKEN
# 
# Формат токена обычно: "381764678:TEST:157405" для тестового режима
# или "390540012:LIVE:85359" для продакшена
PROVIDER_TOKEN_TEST = os.getenv("PROVIDER_TOKEN_TEST", "").strip()
PROVIDER_TOKEN_LIVE = os.getenv("PROVIDER_TOKEN_LIVE", "").strip()

# Обрабатываем переменную TELEGRAM_PAYMENTS_TEST с учетом разных форматов
_telegram_payments_test_raw = os.getenv("TELEGRAM_PAYMENTS_TEST", "True").strip()
TELEGRAM_PAYMENTS_TEST = _telegram_payments_test_raw.lower() in ("true", "1", "yes", "on")

# Выбираем токен в зависимости от режима
provider_token = PROVIDER_TOKEN_TEST if TELEGRAM_PAYMENTS_TEST else PROVIDER_TOKEN_LIVE

logger = logging.getLogger(__name__)
payment_logger = logging.getLogger("payments")
if not payment_logger.handlers:
    from logging.handlers import RotatingFileHandler
    # Ротация для payments.log (макс 5 МБ, 3 резервные копии)
    payment_handler = RotatingFileHandler(
        "payments.log",
        maxBytes=5*1024*1024,  # 5 МБ
        backupCount=3,
        encoding="utf-8"
    )
    payment_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    payment_logger.addHandler(payment_handler)
payment_logger.setLevel(logging.INFO)

# Логируем информацию о токене при загрузке модуля (без полного токена для безопасности)
if provider_token:
    logger.info(f"Provider token загружен. Режим: {'TEST' if TELEGRAM_PAYMENTS_TEST else 'LIVE'}, длина токена: {len(provider_token)}")
    logger.info(f"Первые 15 символов токена: {provider_token[:15]}...")
else:
    logger.error(f"Provider token НЕ ЗАГРУЖЕН! TEST mode: {TELEGRAM_PAYMENTS_TEST}")
    logger.error(f"PROVIDER_TOKEN_TEST: {'установлен' if PROVIDER_TOKEN_TEST else 'НЕ установлен'}")
    logger.error(f"PROVIDER_TOKEN_LIVE: {'установлен' if PROVIDER_TOKEN_LIVE else 'НЕ установлен'}")

# Функция для проверки валидности provider_token
def validate_provider_token(token: str) -> bool:
    """
    Проверяет, что provider_token не пустой и имеет правильный формат.
    Для Telegram Payments с ЮKassa токен должен быть непустой строкой.
    Формат токена от @YooKassa обычно: "381764678:TEST:157405" или "390540012:LIVE:85359"
    """
    if not token:
        return False
    # Минимальная проверка: токен должен содержать хотя бы несколько символов
    if len(token) < 10:
        return False
    # Проверка формата: токен должен содержать двоеточия (формат shop_id:mode:token)
    if ':' not in token:
        logger.warning(f"Токен не содержит двоеточий, возможно неправильный формат: {token[:20]}...")
        # Не блокируем, так как формат может быть разным
    return True

# Глобальная переменная для бесплатного периода
FREE_PERIOD_DAYS = 30

# Создаем роутер для обработчиков подписки
router = Router()


@router.message(Command("check_payment_config"))
async def check_payment_config_handler(message: Message, bot: Bot):
    """
    Команда для проверки конфигурации платежей (только для отладки).
    """
    user_id = message.from_user.id
    
    # Явное логирование в консоль и файл
    print(f"=== CHECK_PAYMENT_CONFIG HANDLER CALLED ===")
    print(f"User ID: {user_id}")
    print(f"Message text: {message.text}")
    logger.info(f"=== CHECK_PAYMENT_CONFIG HANDLER CALLED ===")
    logger.info(f"Команда /check_payment_config от user_id={user_id}")
    logger.info(f"Message text: {message.text}")
    
    try:
        # Сначала отправляем простое сообщение для проверки
        await message.answer("⏳ Проверяю конфигурацию...", parse_mode='HTML')
        logger.info(f"Предварительное сообщение отправлено для user_id={user_id}")
        
        # Получаем сырое значение переменной окружения для диагностики
        telegram_payments_test_raw = os.getenv("TELEGRAM_PAYMENTS_TEST", "True").strip()
        
        # Определяем тип токена (TEST или LIVE) по содержимому
        token_type = "Неизвестно"
        if provider_token:
            if ":TEST:" in provider_token:
                token_type = "TEST (тестовый)"
            elif ":LIVE:" in provider_token:
                token_type = "LIVE (продакшен)"
            else:
                token_type = "Неопределен"
        
        config_info = (
            f"🔍 <b>Конфигурация платежей:</b>\n\n"
            f"<b>Режим работы:</b> <b>{'🧪 TEST (тестовый)' if TELEGRAM_PAYMENTS_TEST else '💰 LIVE (продакшен)'}</b>\n"
            f"<b>TELEGRAM_PAYMENTS_TEST из .env:</b> <code>{telegram_payments_test_raw}</code>\n"
            f"<b>Интерпретация:</b> {'True (тестовый режим)' if TELEGRAM_PAYMENTS_TEST else 'False (продакшен)'}\n\n"
            f"<b>Токены:</b>\n"
            f"PROVIDER_TOKEN_TEST: <b>{'✅ установлен' if PROVIDER_TOKEN_TEST else '❌ НЕ установлен'}</b> "
            f"({len(PROVIDER_TOKEN_TEST)} символов)\n"
            f"PROVIDER_TOKEN_LIVE: <b>{'✅ установлен' if PROVIDER_TOKEN_LIVE else '❌ НЕ установлен'}</b> "
            f"({len(PROVIDER_TOKEN_LIVE)} символов)\n\n"
            f"<b>Текущий используемый токен:</b>\n"
            f"Статус: <b>{'✅ установлен' if provider_token else '❌ НЕ установлен'}</b>\n"
            f"Длина: {len(provider_token) if provider_token else 0} символов\n"
            f"Тип токена: <b>{token_type}</b>\n"
            f"Валидность: <b>{'✅ Валиден' if validate_provider_token(provider_token) else '❌ Невалиден'}</b>\n\n"
        )
        
        if provider_token:
            config_info += f"Первые 20 символов токена: <code>{provider_token[:20]}...</code>\n"
            config_info += f"Последние 10 символов токена: <code>...{provider_token[-10:]}</code>\n"
        
        logger.info(f"Формирование конфигурации завершено для user_id={user_id}")
        logger.info(f"Длина config_info: {len(config_info)} символов")
        
        await message.answer(config_info, parse_mode='HTML')
        logger.info(f"Конфигурация успешно отправлена для user_id={user_id}")
        print(f"=== CONFIG SENT SUCCESSFULLY ===")
        
    except Exception as e:
        error_msg = str(e)
        print(f"=== ERROR IN CHECK_PAYMENT_CONFIG ===")
        print(f"Error: {error_msg}")
        logger.error(f"ОШИБКА в check_payment_config_handler для user_id={user_id}: {error_msg}", exc_info=True)
        try:
            await message.answer(
                f"❌ Ошибка при получении конфигурации:\n\n<code>{error_msg}</code>",
                parse_mode='HTML'
            )
        except Exception as e2:
            logger.error(f"Не удалось отправить сообщение об ошибке: {e2}", exc_info=True)


@router.message(Command("subscribe"))
async def subscribe_handler(message: Message, bot: Bot, state: FSMContext):
    """
    Обработчик для команды /subscribe.
    Активирует бесплатный период на 30 дней (1 месяц) или показывает статус и платные тарифы.
    """
    user_id = message.from_user.id
    user_data = get_user(user_id)
    
    logger.info(f"Команда /subscribe от user_id={user_id}")
    
    # Проверяем, был ли уже активирован бесплатный период
    free_period_start = user_data.get('free_period_start')
    
    if free_period_start is None:
        # Бесплатный период еще не активирован - показываем предложение
        welcome_text = (
            "🎉 <b>Специальное предложение для новых пользователей!</b> 🎉\n\n"
            "Получите <b>полный доступ ко всем функциям бота на 1 месяц БЕСПЛАТНО!</b>\n\n"
            "✨ <b>Что вас ждет:</b>\n"
            "💬 <b>Безграничные диалоги с AI-Духовником</b> — личный наставник 24/7, который понимает вас и поддерживает в любой ситуации\n"
            "📖 <b>Ежедневное «Слово Дня»</b> — глубокие размышления и вдохновение из Писания\n"
            "🙏 <b>Персональные молитвы</b> — составьте молитву о здоровье, семье, делах или любой жизненной ситуации\n"
            "🗓️ <b>Православный календарь</b> — праздники, посты, именины с подробностями\n"
            "⚙️ <b>Умные уведомления</b> — утреннее вдохновение, вечерние размышления\n"
            "⭐ <b>Избранное</b> — сохраняйте важные моменты и молитвы\n\n"
            "💡 <b>Без рекламы. Без ограничений. Все функции открыты!</b>\n\n"
            "📢 <b>Поделитесь ботом с друзьями!</b> Помогите близким найти духовную поддержку.\n\n"
            "👇 Нажмите кнопку ниже, чтобы активировать бесплатный доступ прямо сейчас!"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎁 Активировать бесплатно на 1 месяц", callback_data="activate_free_period")]
        ])
        
        await message.answer(welcome_text, parse_mode='HTML', reply_markup=keyboard)
        logger.info(f"Показано предложение бесплатного периода для user_id={user_id}")
        
    else:
        # Бесплатный период уже активирован - показываем статус
        if isinstance(free_period_start, str):
            try:
                free_period_start = datetime.fromisoformat(free_period_start)
            except (ValueError, TypeError):
                # Данные повреждены - логируем и считаем период истекшим
                logger.error(f"Поврежденная дата free_period_start для user_id={user_id}: {free_period_start}")
                # Устанавливаем дату в прошлое, чтобы период считался истекшим
                free_period_start = datetime.now() - timedelta(days=FREE_PERIOD_DAYS + 1)
                # Исправляем данные в user_data перед сохранением
                user_data['free_period_start'] = free_period_start
                # Сбрасываем статус
                user_data['status'] = 'free_limit'
                save_user_db()
        
        free_period_end = free_period_start + timedelta(days=FREE_PERIOD_DAYS)
        days_left = (free_period_end - datetime.now()).days
        
        if days_left > 0:
            # Бесплатный период еще активен
            status_text = (
                f"✅ <b>Ваш бесплатный период активен!</b>\n\n"
                f"📅 <b>Осталось дней:</b> {days_left}\n"
                f"🗓️ <b>Действует до:</b> {free_period_end.strftime('%d.%m.%Y')}\n\n"
                f"💫 Наслаждайтесь всеми функциями бота без ограничений!\n\n"
            )
            
            # Если осталось меньше 30 дней, показываем предложение о подписке
            if days_left <= 30:
                status_text += (
                    "⏰ <b>Не теряйте доступ!</b>\n"
                    "Оформите Premium-подписку сейчас по специальной цене:\n\n"
                )
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="1 месяц — 399 руб", callback_data="subscribe_1month")],
                    [InlineKeyboardButton(text="3 месяца — 999 руб (-17%)", callback_data="subscribe_3month")],
                    [InlineKeyboardButton(text="Год — 3490 руб (-27%)", callback_data="subscribe_12month")]
                ])
                await message.answer(status_text, parse_mode='HTML', reply_markup=keyboard)
            else:
                await message.answer(status_text, parse_mode='HTML')
                
            logger.info(f"Показан статус бесплатного периода для user_id={user_id}, осталось дней: {days_left}")
            
        else:
            # Бесплатный период истек - показываем платные тарифы
            expired_text = (
                "⏰ <b>Ваш бесплатный период завершен</b>\n\n"
                "Спасибо, что были с нами этот месяц! Надеемся, бот принес вам пользу и духовную поддержку.\n\n"
                "🌟 <b>Продолжайте путь духовного роста с Premium-подпиской:</b>\n"
                "💬 Безграничные диалоги с AI-Духовником\n"
                "📖 Ежедневное «Слово Дня» с размышлениями\n"
                "🙏 Персональные молитвы\n"
                "🗓️ Расширенный православный календарь\n"
                "⚙️ Умные уведомления\n\n"
                "💎 <b>Выберите тариф:</b>"
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="1 месяц — 399 руб", callback_data="subscribe_1month")],
                [InlineKeyboardButton(text="3 месяца — 999 руб (экономия 198 руб)", callback_data="subscribe_3month")],
                [InlineKeyboardButton(text="Год — 3490 руб (экономия 1298 руб)", callback_data="subscribe_12month")]
            ])
            
            await message.answer(expired_text, parse_mode='HTML', reply_markup=keyboard)
            logger.info(f"Показаны платные тарифы для user_id={user_id} (бесплатный период истек)")


@router.callback_query(F.data == "activate_free_period")
async def activate_free_period_handler(callback_query: CallbackQuery, bot: Bot):
    """
    Обработчик активации бесплатного периода на 30 дней (1 месяц).
    """
    user_id = callback_query.from_user.id
    user_data = get_user(user_id)
    
    logger.info(f"Активация бесплатного периода для user_id={user_id}")
    
    # Проверяем, не был ли уже активирован бесплатный период
    if user_data.get('free_period_start') is not None:
        await callback_query.answer("Бесплатный период уже был активирован!", show_alert=True)
        return
    
    # Активируем бесплатный период
    user_data['free_period_start'] = datetime.now()
    user_data['status'] = 'free_active'
    save_user_db()
    
    free_period_end = datetime.now() + timedelta(days=FREE_PERIOD_DAYS)
    
    success_text = (
        "🎉 <b>Поздравляем! Полный доступ активирован!</b> 🎉\n\n"
        f"✅ Вы получили <b>1 месяц бесплатного доступа</b> ко всем функциям бота!\n"
        f"📅 <b>Действует до:</b> {free_period_end.strftime('%d.%m.%Y')}\n\n"
        "🌟 <b>Теперь вам доступно:</b>\n"
        "💬 Безграничные диалоги с AI-Духовником — задавайте любые вопросы о вере\n"
        "📖 Ежедневное «Слово Дня» — глубокие размышления каждый день в 14:00\n"
        "🙏 Персональные молитвы — составьте молитву на любую тему\n"
        "🗓️ Полный православный календарь — праздники, посты, именины\n"
        "⚙️ Умные уведомления — утреннее вдохновение (8:00) и вечерние размышления (20:00)\n"
        "⭐ Избранное — сохраняйте важные моменты\n\n"
        "💡 <b>Начните прямо сейчас:</b>\n"
        "• Спросите что-то у бота\n"
        "• Попросите составить молитву (/prayer)\n"
        "• Посмотрите православный календарь (/calendar)\n"
        "• Настройте уведомления (/settings)\n\n"
        "📢 <b>Поделитесь ботом с друзьями!</b>\n"
        "Расскажите близким об этой возможности — пусть они тоже получат 1 месяц бесплатного доступа к духовной поддержке!\n\n"
        "🙏 Благодарим за доверие! Пусть бот станет вашим верным спутником на пути духовного роста."
    )
    
    await callback_query.message.edit_text(success_text, parse_mode='HTML')
    await callback_query.answer("🎉 Доступ активирован!")
    
    logger.info(f"Бесплатный период активирован для user_id={user_id} до {free_period_end.strftime('%d.%m.%Y')}")
    payment_logger.info(f"FREE_PERIOD_ACTIVATED user_id={user_id} days={FREE_PERIOD_DAYS} end_date={free_period_end.isoformat()}")


@router.message(Command("status"))
async def status_handler(message: Message):
    """
    Команда для просмотра статуса подписки и истории платежей.
    """
    user_id = message.from_user.id
    
    logger.info(f"Команда /status от user_id={user_id}")
    
    try:
        user_data = get_user(user_id)
        status = user_data.get('status', 'free')
        end_date = user_data.get('subscription_end_date')
        
        if end_date:
            end_date_str = end_date.strftime('%d.%m.%Y')
        else:
            end_date_str = 'нет'
        
        # Получаем историю платежей
        payments = user_data.get('payments', [])
        if payments:
            payments_text = "\n".join([
                f"• {payment.get('date', 'Неизвестно')} — {payment.get('amount', 0) / 100:.2f} руб ({payment.get('period', 'N/A')})"
                for payment in payments
            ])
        else:
            payments_text = 'нет'
        
        text = (
            f"Ваш статус: {status}\n"
            f"Дата окончания: {end_date_str}\n\n"
            f"История платежей:\n{payments_text}"
        )
        
        logger.info(f"Статус отправлен для user_id={user_id}: status={status}, payments_count={len(payments) if payments else 0}")
        await message.answer(text)
        
    except Exception as e:
        logger.error(f"Ошибка при получении статуса для user_id={user_id}: {e}", exc_info=True)
        await message.answer(
            "❌ <b>Произошла ошибка при получении статуса.</b>\n\n"
            "Пожалуйста, попробуйте позже или обратитесь в поддержку: /support",
            parse_mode='HTML'
        )


async def send_invoice_for_tariff(bot: Bot, chat_id: int, user_id: int, tariff: str, amount: int, days: int):
    """
    Вспомогательная функция для отправки invoice для выбранного тарифа.
    """
    # Формируем payload с информацией о тарифе и днях
    payload = f"premium_{days}_days_{user_id}_{int(datetime.now().timestamp())}"
    
    # Определяем название тарифа
    if days == 30:
        title = "Premium «Духовник» на 1 месяц"
        label = "Premium 1 месяц"
        duration_text = "1 месяц"
    elif days == 90:
        title = "Premium «Духовник» на 3 месяца"
        label = "Premium 3 месяца"
        duration_text = "3 месяца"
    elif days == 365:
        title = "Premium «Духовник» на 1 год"
        label = "Premium 1 год"
        duration_text = "1 год"
    else:
        title = f"Premium «Духовник» на {days} дней"
        label = f"Premium {days} дней"
        duration_text = f"{days} дней"
    
    logger.info(f"Попытка отправить invoice для тарифа {tariff} пользователю {user_id}. Режим: {'TEST' if TELEGRAM_PAYMENTS_TEST else 'LIVE'}, amount={amount}, days={days}")
    
    # Формируем чек по 54-ФЗ
    import json
    provider_data = {
        "receipt": {
            "items": [
                {
                    "description": f"Premium «Духовник» на {duration_text}",
                    "quantity": "1",
                    "amount": {
                        "value": f"{amount / 100:.2f}",
                        "currency": "RUB"
                    },
                    "vat_code": 6,  # Для самозанятых на НПД (без НДС)
                    "payment_mode": "full_payment",
                    "payment_subject": "service"
                }
            ]
        }
    }
    
    # Добавляем email пользователя в чек, если он есть в базе
    user_data = get_user(user_id)
    user_email = user_data.get('email')
    if user_email:
        provider_data["receipt"]["customer"] = {"email": user_email}
        logger.info(f"Email пользователя добавлен в чек: {user_email}")
    
    provider_data_json = json.dumps(provider_data)
    logger.info(f"Чек сформирован для user_id={user_id}, provider_data={provider_data_json}")
    
    # Отправляем invoice
    await bot.send_invoice(
        chat_id=chat_id,
        title=title,
        description="Безграничный доступ к AI-собеседнику, Слову дня и молитвам",
        payload=payload,
        provider_token=provider_token,
        currency="RUB",
        prices=[LabeledPrice(label=label, amount=amount)],
        provider_data=provider_data_json
    )
    
    logger.info(f"Invoice отправлен для user_id={user_id}, payload={payload}, tariff={tariff}")


@router.callback_query(F.data == "subscribe_1month")
async def subscribe_1month_handler(callback_query: CallbackQuery, bot: Bot, state: FSMContext):
    """
    Обработчик для тарифа "1 месяц".
    """
    user_id = callback_query.from_user.id
    
    logger.info(f"Выбран тариф 1 месяц от user_id={user_id}")
    
    # Проверяем наличие provider_token
    if not validate_provider_token(provider_token):
        await callback_query.message.answer(
            "❌ <b>Ошибка конфигурации платежей.</b>\n\n"
            "Платежная система не настроена.",
            parse_mode='HTML'
        )
        await callback_query.answer()
        return
    
    try:
        await send_invoice_for_tariff(bot, callback_query.message.chat.id, user_id, "1month", 39900, 30)
        await callback_query.answer()
    except Exception as e:
        logger.exception(e)
        await callback_query.message.answer(
            "❌ <b>Произошла ошибка при создании платежа.</b>\n\n"
            "Пожалуйста, попробуйте позже или обратитесь в поддержку: /support",
            parse_mode='HTML'
        )
        await callback_query.answer()


@router.callback_query(F.data == "subscribe_3month")
async def subscribe_3month_handler(callback_query: CallbackQuery, bot: Bot, state: FSMContext):
    """
    Обработчик для тарифа "3 месяца".
    """
    user_id = callback_query.from_user.id
    
    logger.info(f"Выбран тариф 3 месяца от user_id={user_id}")
    
    # Проверяем наличие provider_token
    if not validate_provider_token(provider_token):
        await callback_query.message.answer(
            "❌ <b>Ошибка конфигурации платежей.</b>\n\n"
            "Платежная система не настроена.",
            parse_mode='HTML'
        )
        await callback_query.answer()
        return
    
    try:
        await send_invoice_for_tariff(bot, callback_query.message.chat.id, user_id, "3month", 99900, 90)
        await callback_query.answer()
    except Exception as e:
        logger.exception(e)
        await callback_query.message.answer(
            "❌ <b>Произошла ошибка при создании платежа.</b>\n\n"
            "Пожалуйста, попробуйте позже или обратитесь в поддержку: /support",
            parse_mode='HTML'
        )
        await callback_query.answer()


@router.callback_query(F.data == "subscribe_12month")
async def subscribe_12month_handler(callback_query: CallbackQuery, bot: Bot, state: FSMContext):
    """
    Обработчик для тарифа "12 месяцев".
    """
    user_id = callback_query.from_user.id
    
    logger.info(f"Выбран тариф 12 месяцев от user_id={user_id}")
    
    # Проверяем наличие provider_token
    if not validate_provider_token(provider_token):
        await callback_query.message.answer(
            "❌ <b>Ошибка конфигурации платежей.</b>\n\n"
            "Платежная система не настроена.",
            parse_mode='HTML'
        )
        await callback_query.answer()
        return
    
    try:
        await send_invoice_for_tariff(bot, callback_query.message.chat.id, user_id, "12month", 349000, 365)
        await callback_query.answer()
    except Exception as e:
        logger.exception(e)
        await callback_query.message.answer(
            "❌ <b>Произошла ошибка при создании платежа.</b>\n\n"
            "Пожалуйста, попробуйте позже или обратитесь в поддержку: /support",
            parse_mode='HTML'
        )
        await callback_query.answer()


@router.callback_query(F.data == "subscribe_premium")
async def subscribe_callback_handler(callback_query: CallbackQuery, bot: Bot, state: FSMContext):
    """
    Обработчик для кнопки "Оформить Premium".
    Отправляет invoice через Telegram Payments с ЮKassa.
    """
    user_id = callback_query.from_user.id
    
    logger.info(f"Кнопка 'Оформить Premium' от user_id={user_id}")
    
    # Проверяем наличие provider_token
    if not validate_provider_token(provider_token):
        logger.error(f"Provider token не настроен или невалиден. TEST mode: {TELEGRAM_PAYMENTS_TEST}")
        logger.error(f"PROVIDER_TOKEN_TEST: {'установлен' if PROVIDER_TOKEN_TEST else 'НЕ установлен'}")
        logger.error(f"PROVIDER_TOKEN_LIVE: {'установлен' if PROVIDER_TOKEN_LIVE else 'НЕ установлен'}")
        await callback_query.message.answer(
            "❌ <b>Ошибка конфигурации платежей.</b>\n\n"
            "Платежная система не настроена.\n\n"
            "<b>Как настроить:</b>\n"
            "1. Откройте @BotFather в Telegram\n"
            "2. Выполните /mybots → выберите бота → Payments\n"
            "3. Подключите ЮKassa (тест или продакшен)\n"
            "4. Скопируйте токен в .env файл как PROVIDER_TOKEN_TEST или PROVIDER_TOKEN_LIVE\n\n"
            "Подробная инструкция: https://yookassa.ru/docs/support/payments/onboarding/integration/cms-module/telegram",
            parse_mode='HTML'
        )
        await callback_query.answer()
        return
    
    # Не активируем пробный период в старом обработчике - он активируется автоматически через middleware
    # При выборе тарифа пользователь должен оплатить подписку
    logger.info(f"Кнопка 'Оформить Premium' обработана для user_id={user_id}")
    
    try:
        # Формируем payload с уникальным идентификатором
        payload = f"premium_30_days_{user_id}_{int(datetime.now().timestamp())}"
        
        logger.info(f"Попытка отправить invoice пользователю {user_id}. Режим: {'TEST' if TELEGRAM_PAYMENTS_TEST else 'LIVE'}, provider_token (первые 15 символов): {provider_token[:15] if provider_token else 'None'}..., длина токена: {len(provider_token) if provider_token else 0}")
        
        # Формируем чек по 54-ФЗ
        import json
        provider_data = {
            "receipt": {
                "items": [
                    {
                        "description": "Premium «Духовник» на 1 месяц",
                        "quantity": "1",
                        "amount": {
                            "value": "399.00",
                            "currency": "RUB"
                        },
                        "vat_code": 6,  # Для самозанятых на НПД (без НДС)
                        "payment_mode": "full_payment",
                        "payment_subject": "service"
                    }
                ]
            }
        }
        
        # Добавляем email пользователя в чек, если он есть в базе
        user_data = get_user(user_id)
        user_email = user_data.get('email')
        if user_email:
            provider_data["receipt"]["customer"] = {"email": user_email}
            logger.info(f"Email пользователя добавлен в чек: {user_email}")
        
        provider_data_json = json.dumps(provider_data)
        logger.info(f"Чек сформирован для user_id={user_id}, provider_data={provider_data_json}")
        
        # Отправляем invoice
        await bot.send_invoice(
            chat_id=callback_query.message.chat.id,
            title="Premium «Духовник» на 30 дней",
            description="Безграничный доступ к AI-собеседнику, Слову дня и молитвам",
            payload=payload,
            provider_token=provider_token,
            currency="RUB",
            prices=[LabeledPrice(label="Premium 30 дней", amount=39900)],  # 399 рублей = 39900 копеек
            provider_data=provider_data_json
        )
        
        logger.info(f"Invoice отправлен для user_id={user_id}, payload={payload}")
        await callback_query.answer()
        
    except Exception as e:
        error_message = str(e)
        error_type = type(e).__name__
        logger.exception(e)
        
        # Более детальное сообщение об ошибке для отладки
        if "provider_token" in error_message.lower() or "invalid" in error_message.lower() or "bad request" in error_message.lower():
            error_text = (
                "❌ <b>Ошибка при создании платежа.</b>\n\n"
                "Проблема с настройкой платежного провайдера.\n\n"
                "<b>Возможные причины:</b>\n"
                "• Токен неверный или устарел\n"
                "• Бот не подключен к ЮKassa через @BotFather\n"
                "• Магазин не работает на протоколе API\n\n"
                f"Тип ошибки: {error_type}\n\n"
                "Проверьте настройки через команду /check_payment_config\n"
                "Инструкция: https://yookassa.ru/docs/support/payments/onboarding/integration/cms-module/telegram"
            )
        elif "unauthorized" in error_message.lower() or "401" in error_message.lower():
            error_text = (
                "❌ <b>Ошибка авторизации.</b>\n\n"
                "Токен платежного провайдера неверный или истек срок действия.\n\n"
                f"Тип ошибки: {error_type}\n\n"
                "Проверьте токен через @BotFather → Payments"
            )
        else:
            error_text = (
                "❌ <b>Произошла ошибка при создании платежа.</b>\n\n"
                f"Тип ошибки: {error_type}\n\n"
                "Пожалуйста, попробуйте позже или обратитесь в поддержку: /support"
            )
        
        await callback_query.message.answer(error_text, parse_mode='HTML')
        await callback_query.answer()


@router.pre_checkout_query()
async def pre_checkout_handler(query: PreCheckoutQuery, bot: Bot):
    """
    Обработчик pre-checkout запроса.
    Подтверждает платеж перед его выполнением.
    """
    user_id = query.from_user.id
    invoice_payload = query.invoice_payload
    
    logger.info(f"Pre-checkout запрос для user_id={user_id}, payload={invoice_payload}")
    
    try:
        # Подтверждаем возможность оплаты
        await bot.answer_pre_checkout_query(
            pre_checkout_query_id=query.id,
            ok=True
        )
        logger.info(f"Pre-checkout запрос подтвержден для user_id={user_id}")
    except Exception as e:
        logger.error(f"Ошибка при обработке pre_checkout_query для user_id={user_id}: {e}", exc_info=True)
        try:
            await bot.answer_pre_checkout_query(
                pre_checkout_query_id=query.id,
                ok=False,
                error_message="Произошла ошибка при обработке платежа. Пожалуйста, попробуйте позже."
            )
        except Exception:
            pass


@router.message(F.successful_payment)
async def successful_payment_handler(message: Message, bot: Bot):
    """
    Обработчик успешного платежа.
    Активирует Premium подписку на указанное количество дней из payload.
    """
    user_id = message.from_user.id
    payment_info = message.successful_payment
    payload = payment_info.invoice_payload
    
    logger.info(f"Оплата прошла для user_id={user_id}, invoice_payload={payload}, total_amount={payment_info.total_amount}")
    payment_logger.info(f"SUCCESS user_id={user_id} amount={payment_info.total_amount} payload={payload}")
    
    try:
        # Парсим количество дней из payload
        # Формат: premium_{days}_days_{user_id}_{timestamp}
        days = 30  # значение по умолчанию
        try:
            # Извлекаем days из payload
            parts = payload.split('_')
            if len(parts) >= 2 and parts[0] == 'premium':
                days = int(parts[1])
                logger.info(f"Извлечено количество дней из payload: {days}")
        except (ValueError, IndexError) as e:
            logger.warning(f"Не удалось извлечь количество дней из payload '{payload}': {e}. Используется значение по умолчанию: 30")
        
        # Активируем Premium подписку на указанное количество дней
        success = await activate_premium_subscription(user_id, duration_days=days)
        
        if success:
            # Обновляем статус в user_db
            user_data = get_user(user_id)
            user_data['subscription_end_date'] = datetime.now() + timedelta(days=days)
            user_data['status'] = 'active'
            
            # Сохраняем информацию о платеже в историю
            if 'payments' not in user_data:
                user_data['payments'] = []
            
            # Формируем текст периода для истории
            if days == 30:
                period_text = "1 месяц"
            elif days == 90:
                period_text = "3 месяца"
            elif days == 365:
                period_text = "1 год"
            else:
                period_text = f"{days} дней"
            
            payment_record = {
                'date': datetime.now().strftime('%d.%m.%Y %H:%M'),
                'amount': payment_info.total_amount,
                'period': period_text,
                'payload': payload
            }
            user_data['payments'].append(payment_record)
            save_user_db()  # Сохраняем изменения
            
            logger.info(f"Premium подписка успешно активирована для user_id={user_id} на {days} дней. Платеж сохранен в историю.")
            payment_logger.info(f"ACTIVATED user_id={user_id} days={days} end_date={user_data.get('subscription_end_date')}")
            
            await message.answer(
                f"🎉 <b>Оплата прошла! Premium активирован на {period_text}!</b> 🎉\n\n"
                "Теперь у вас есть доступ ко всем Premium функциям:\n"
                "💬 Безграничные диалоги с AI-Собеседником\n"
                "📖 Ежедневное «Слово Дня» с AI-размышлением\n"
                "🙏 Помощь в составлении молитв\n"
                "🗓️ Расширенный Православный Календарь\n"
                "⚙️ Персонализированные уведомления\n\n"
                "Желаем вам духовного роста и гармонии! 🙏",
                parse_mode='HTML'
            )
        else:
            logger.error(f"Ошибка при активации Premium подписки для user_id={user_id}")
            payment_logger.error(f"FAILED_ACTIVATION user_id={user_id} payload={payload}")
            await message.answer(
                "❌ <b>Произошла ошибка при активации Premium подписки.</b>\n\n"
                "Пожалуйста, обратитесь в поддержку: /support",
                parse_mode='HTML'
            )
            
    except Exception as e:
        logger.error(f"Ошибка при обработке успешного платежа для user_id={user_id}: {e}", exc_info=True)
        payment_logger.error(f"ERROR_SUCCESS_HANDLER user_id={user_id} payload={payload} error={e}")
        await message.answer(
            "❌ <b>Произошла ошибка при обработке платежа.</b>\n\n"
            "Пожалуйста, обратитесь в поддержку: /support",
            parse_mode='HTML'
        )


@router.message(F.recurring_payment)
async def recurring_payment_handler(message: Message, bot: Bot):
    """
    Обработчик автопродления подписки.
    Продлевает подписку на 30 дней автоматически.
    """
    user_id = message.from_user.id
    recurring_payment = message.recurring_payment
    
    logger.info(f"Автопродление для user_id={user_id}, invoice_payload={recurring_payment.invoice_payload}, total_amount={recurring_payment.total_amount}")
    payment_logger.info(f"RECURRING user_id={user_id} amount={recurring_payment.total_amount} payload={recurring_payment.invoice_payload}")
    
    try:
        # Продлеваем подписку на 30 дней
        days = 30
        success = await activate_premium_subscription(user_id, duration_days=days)
        
        if success:
            # Обновляем статус в user_db
            user_data = get_user(user_id)
            current_end_date = user_data.get('subscription_end_date')
            
            # Если подписка уже активна, продлеваем от текущей даты окончания, иначе от текущей даты
            if current_end_date and current_end_date > datetime.now():
                user_data['subscription_end_date'] = current_end_date + timedelta(days=days)
            else:
                user_data['subscription_end_date'] = datetime.now() + timedelta(days=days)
            
            user_data['status'] = 'active'
            
            # Сохраняем информацию о платеже автопродления в историю
            if 'payments' not in user_data:
                user_data['payments'] = []
            
            payment_record = {
                'date': datetime.now().strftime('%d.%m.%Y %H:%M'),
                'amount': recurring_payment.total_amount,
                'period': '1 месяц (автопродление)',
                'payload': recurring_payment.invoice_payload
            }
            user_data['payments'].append(payment_record)
            save_user_db()  # Сохраняем изменения
            
            logger.info(f"Автопродление успешно выполнено для user_id={user_id}. Подписка продлена на {days} дней.")
            payment_logger.info(f"RENEWED user_id={user_id} days={days} end_date={user_data.get('subscription_end_date')}")
            
            await message.answer(
                "🔄 <b>Подписка автоматически продлена на 1 месяц!</b> 🔄\n\n"
                "Ваша Premium подписка продолжает действовать.\n\n"
                "Спасибо за доверие! 🙏",
                parse_mode='HTML'
            )
        else:
            logger.error(f"Ошибка при автопродлении подписки для user_id={user_id}")
            payment_logger.error(f"FAILED_RENEWAL user_id={user_id} payload={recurring_payment.invoice_payload}")
            await message.answer(
                "❌ <b>Произошла ошибка при автопродлении подписки.</b>\n\n"
                "Пожалуйста, обратитесь в поддержку: /support",
                parse_mode='HTML'
            )
            
    except Exception as e:
        logger.error(f"Ошибка при обработке автопродления для user_id={user_id}: {e}", exc_info=True)
        payment_logger.error(f"ERROR_RECURRING_HANDLER user_id={user_id} payload={recurring_payment.invoice_payload} error={e}")
        await message.answer(
            "❌ <b>Произошла ошибка при обработке автопродления.</b>\n\n"
            "Пожалуйста, обратитесь в поддержку: /support",
            parse_mode='HTML'
        )


@router.message(Command("cancel_subscription"))
async def cancel_subscription_handler(message: Message):
    """
    Команда для отмены подписки.
    Меняет статус на 'canceled'.
    """
    user_id = message.from_user.id
    
    logger.info(f"Команда /cancel_subscription от user_id={user_id}")
    
    try:
        user_data = get_user(user_id)
        current_status = user_data.get('status', 'free')
        
        if current_status == 'canceled':
            await message.answer("Подписка уже отменена.")
            logger.info(f"Попытка отменить уже отмененную подписку для user_id={user_id}")
            return
        
        # Меняем статус на 'canceled'
        user_data['status'] = 'canceled'
        save_user_db()  # Сохраняем изменения
        
        logger.info(f"Подписка отменена для user_id={user_id}. Предыдущий статус: {current_status}")
        
        await message.answer("Подписка отменена.")
        
    except Exception as e:
        logger.error(f"Ошибка при отмене подписки для user_id={user_id}: {e}", exc_info=True)
        await message.answer(
            "❌ <b>Произошла ошибка при отмене подписки.</b>\n\n"
            "Пожалуйста, попробуйте позже или обратитесь в поддержку: /support",
            parse_mode='HTML'
        )


__all__ = ["router"]

