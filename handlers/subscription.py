import os
import logging
from datetime import datetime, timedelta
from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.types import Message, PreCheckoutQuery, LabeledPrice, CallbackQuery
from aiogram.fsm.context import FSMContext
from dotenv import load_dotenv
from core.user_database import user_db, get_user
from core.subscription_checker import activate_premium_subscription, activate_trial

load_dotenv()

# Получаем токены из .env
# ВАЖНО: PROVIDER_TOKEN - это токен для Telegram Payments, который выдается через бота @YooKassa
# Это НЕ токен от ЮKassa API напрямую. Чтобы получить токен:
# 1. Откройте бота @YooKassa в Telegram
# 2. Выполните команду /start
# 3. Подключите ваш магазин (shop_id)
# 4. Бот выдаст вам токен для Telegram Payments
# Формат токена обычно: "381764678:TEST:157405" для тестового режима
PROVIDER_TOKEN_TEST = os.getenv("PROVIDER_TOKEN_TEST", "").strip()
PROVIDER_TOKEN_LIVE = os.getenv("PROVIDER_TOKEN_LIVE", "").strip()
TELEGRAM_PAYMENTS_TEST = os.getenv("TELEGRAM_PAYMENTS_TEST", "True").lower() == "true"

# Выбираем токен в зависимости от режима
provider_token = PROVIDER_TOKEN_TEST if TELEGRAM_PAYMENTS_TEST else PROVIDER_TOKEN_LIVE

logger = logging.getLogger(__name__)

# Функция для проверки валидности provider_token
def validate_provider_token(token: str) -> bool:
    """
    Проверяет, что provider_token не пустой и имеет правильный формат.
    Для Telegram Payments с ЮKassa токен должен быть непустой строкой.
    """
    if not token:
        return False
    # Минимальная проверка: токен должен содержать хотя бы несколько символов
    if len(token) < 10:
        return False
    return True

# Создаем роутер для обработчиков подписки
router = Router()


@router.message(Command("subscribe"))
async def subscribe_handler(message: Message, bot: Bot, state: FSMContext):
    """
    Обработчик для команды /subscribe.
    Отправляет invoice через Telegram Payments с ЮKassa.
    """
    user_id = message.from_user.id
    
    logger.info(f"Команда /subscribe от user_id={user_id}")
    
    # Проверяем наличие provider_token
    if not validate_provider_token(provider_token):
        logger.error(f"Provider token не настроен или невалиден. TEST mode: {TELEGRAM_PAYMENTS_TEST}")
        await message.answer(
            "❌ <b>Ошибка конфигурации платежей.</b>\n\n"
            "Платежная система не настроена. Пожалуйста, обратитесь в поддержку: /support",
            parse_mode='HTML'
        )
        return
    
    # Активируем бесплатный период, если он еще не был активирован
    await activate_trial(user_id)
    logger.info(f"Бесплатный период активирован/проверен для user_id={user_id}")
    
    try:
        # Формируем payload с уникальным идентификатором
        payload = f"premium_30_days_{user_id}_{int(datetime.now().timestamp())}"
        
        logger.info(f"Отправка invoice для user_id={user_id}, provider_token (первые 10 символов): {provider_token[:10]}...")
        
        # Отправляем invoice
        await bot.send_invoice(
            chat_id=message.chat.id,
            title="Premium «Духовник» на 30 дней",
            description="Безграничный доступ к AI-собеседнику, Слову дня и молитвам",
            payload=payload,
            provider_token=provider_token,
            currency="RUB",
            prices=[LabeledPrice(label="Premium 30 дней", amount=29900)],  # 299 рублей = 29900 копеек
        )
        
        logger.info(f"Invoice отправлен для user_id={user_id}, payload={payload}")
        
    except Exception as e:
        error_message = str(e)
        logger.error(f"Ошибка при отправке invoice для user_id={user_id}: {error_message}", exc_info=True)
        
        # Более детальное сообщение об ошибке для отладки
        if "provider_token" in error_message.lower() or "invalid" in error_message.lower():
            error_text = (
                "❌ <b>Ошибка при создании платежа.</b>\n\n"
                "Проблема с настройкой платежного провайдера. "
                "Пожалуйста, обратитесь в поддержку: /support"
            )
        else:
            error_text = (
                "❌ <b>Произошла ошибка при создании платежа.</b>\n\n"
                "Пожалуйста, попробуйте позже или обратитесь в поддержку: /support"
            )
        
        await message.answer(error_text, parse_mode='HTML')


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
        await callback_query.message.answer(
            "❌ <b>Ошибка конфигурации платежей.</b>\n\n"
            "Платежная система не настроена. Пожалуйста, обратитесь в поддержку: /support",
            parse_mode='HTML'
        )
        await callback_query.answer()
        return
    
    # Активируем бесплатный период, если он еще не был активирован
    await activate_trial(user_id)
    logger.info(f"Бесплатный период активирован/проверен для user_id={user_id}")
    
    try:
        # Формируем payload с уникальным идентификатором
        payload = f"premium_30_days_{user_id}_{int(datetime.now().timestamp())}"
        
        logger.info(f"Отправка invoice для user_id={user_id}, provider_token (первые 10 символов): {provider_token[:10]}...")
        
        # Отправляем invoice
        await bot.send_invoice(
            chat_id=callback_query.message.chat.id,
            title="Premium «Духовник» на 30 дней",
            description="Безграничный доступ к AI-собеседнику, Слову дня и молитвам",
            payload=payload,
            provider_token=provider_token,
            currency="RUB",
            prices=[LabeledPrice(label="Premium 30 дней", amount=29900)],  # 299 рублей = 29900 копеек
        )
        
        logger.info(f"Invoice отправлен для user_id={user_id}, payload={payload}")
        await callback_query.answer()
        
    except Exception as e:
        error_message = str(e)
        logger.error(f"Ошибка при отправке invoice для user_id={user_id}: {error_message}", exc_info=True)
        
        # Более детальное сообщение об ошибке для отладки
        if "provider_token" in error_message.lower() or "invalid" in error_message.lower():
            error_text = (
                "❌ <b>Ошибка при создании платежа.</b>\n\n"
                "Проблема с настройкой платежного провайдера. "
                "Пожалуйста, обратитесь в поддержку: /support"
            )
        else:
            error_text = (
                "❌ <b>Произошла ошибка при создании платежа.</b>\n\n"
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
    Активирует Premium подписку на 30 дней.
    """
    user_id = message.from_user.id
    payment_info = message.successful_payment
    
    logger.info(f"Оплата прошла для user_id={user_id}, invoice_payload={payment_info.invoice_payload}, total_amount={payment_info.total_amount}")
    
    try:
        # Активируем Premium подписку на 30 дней
        success = await activate_premium_subscription(user_id, duration_days=30)
        
        if success:
            # Обновляем статус в user_db
            user_data = get_user(user_id)
            user_data['subscription_end_date'] = datetime.now() + timedelta(days=30)
            user_data['status'] = 'active'
            
            logger.info(f"Premium подписка успешно активирована для user_id={user_id}")
            
            await message.answer(
                "🎉 <b>Оплата прошла! Premium активирован на 30 дней!</b> 🎉\n\n"
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
            await message.answer(
                "❌ <b>Произошла ошибка при активации Premium подписки.</b>\n\n"
                "Пожалуйста, обратитесь в поддержку: /support",
                parse_mode='HTML'
            )
            
    except Exception as e:
        logger.error(f"Ошибка при обработке успешного платежа для user_id={user_id}: {e}", exc_info=True)
        await message.answer(
            "❌ <b>Произошла ошибка при обработке платежа.</b>\n\n"
            "Пожалуйста, обратитесь в поддержку: /support",
            parse_mode='HTML'
        )

