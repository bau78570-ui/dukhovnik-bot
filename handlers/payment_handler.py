"""
Обработчики для работы с платежами через ЮKassa.
Проверка статуса оплаты и активация Premium подписки.
"""
import logging
from datetime import datetime
from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.types import Message, PreCheckoutQuery, LabeledPrice, ContentType
from aiogram.fsm.context import FSMContext
from core.user_database import get_user
from core.subscription_checker import activate_premium_subscription
from payments.yookassa import check_payment_status, is_payment_successful

logger = logging.getLogger(__name__)

# Создаем роутер для обработки платежей
router = Router()


@router.message(Command("check_payment"))
async def check_payment_command_handler(message: Message, bot: Bot, state: FSMContext):
    """
    Команда для ручной проверки статуса платежа.
    Проверяет все pending платежи пользователя.
    """
    user_id = message.from_user.id
    logger.info(f"Команда /check_payment от user_id={user_id}")
    
    try:
        user_data = get_user(user_id)
        pending_payments = user_data.get('pending_payments', {})
        
        if not pending_payments:
            await message.answer(
                "У вас нет ожидающих платежей.\n\n"
                "Оформите Premium подписку: /subscribe"
            )
            return
        
        checked_count = 0
        activated_count = 0
        
        for payment_id, payment_info in list(pending_payments.items()):
            if payment_info.get('status') == 'pending':
                logger.info(f"Проверка платежа payment_id={payment_id} для user_id={user_id}")
                
                try:
                    # Проверяем статус платежа в ЮKassa
                    is_paid = await is_payment_successful(payment_id)
                    
                    if is_paid:
                        logger.info(f"Платеж payment_id={payment_id} успешно оплачен для user_id={user_id}")
                        
                        # Активируем Premium подписку на 30 дней
                        success = await activate_premium_subscription(user_id, duration_days=30)
                        
                        if success:
                            # Обновляем статус платежа
                            payment_info['status'] = 'completed'
                            payment_info['completed_at'] = datetime.now().isoformat()
                            activated_count += 1
                            logger.info(f"Premium подписка активирована для user_id={user_id} после оплаты payment_id={payment_id}")
                        else:
                            logger.error(f"Ошибка при активации Premium для user_id={user_id} после оплаты payment_id={payment_id}")
                    
                    checked_count += 1
                    
                except Exception as e:
                    logger.error(f"Ошибка при проверке платежа payment_id={payment_id} для user_id={user_id}: {e}", exc_info=True)
        
        if activated_count > 0:
            await message.answer(
                f"✨ <b>Отлично! Premium подписка активирована!</b> ✨\n\n"
                f"Проверено платежей: {checked_count}\n"
                f"Активировано подписок: {activated_count}\n\n"
                f"Теперь у вас есть доступ ко всем Premium функциям на 30 дней!",
                parse_mode='HTML'
            )
        elif checked_count > 0:
            await message.answer(
                f"Проверено платежей: {checked_count}\n"
                f"Оплаченных платежей пока нет.\n\n"
                f"Пожалуйста, завершите оплату или попробуйте позже."
            )
        else:
            await message.answer(
                "Не найдено платежей для проверки."
            )
            
    except Exception as e:
        logger.error(f"Ошибка в check_payment_command_handler для user_id={user_id}: {e}", exc_info=True)
        await message.answer(
            "❌ Произошла ошибка при проверке платежей.\n\n"
            "Пожалуйста, попробуйте позже или обратитесь в поддержку: /support"
        )


@router.pre_checkout_query()
async def pre_checkout_query_handler(pre_checkout_query: PreCheckoutQuery, bot: Bot):
    """
    Обработчик pre_checkout_query для Telegram Payments (invoice).
    Подтверждает возможность оплаты.
    """
    user_id = pre_checkout_query.from_user.id
    invoice_payload = pre_checkout_query.invoice_payload
    
    logger.info(f"pre_checkout_query от user_id={user_id}, payload={invoice_payload}")
    
    try:
        # Подтверждаем возможность оплаты
        await bot.answer_pre_checkout_query(
            pre_checkout_query_id=pre_checkout_query.id,
            ok=True
        )
        logger.info(f"pre_checkout_query подтвержден для user_id={user_id}")
        
    except Exception as e:
        logger.error(f"Ошибка при обработке pre_checkout_query для user_id={user_id}: {e}", exc_info=True)
        try:
            await bot.answer_pre_checkout_query(
                pre_checkout_query_id=pre_checkout_query.id,
                ok=False,
                error_message="Произошла ошибка при обработке платежа. Пожалуйста, попробуйте позже."
            )
        except Exception:
            pass


@router.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment_handler(message: Message, bot: Bot, state: FSMContext):
    """
    Обработчик успешной оплаты через Telegram Payments (invoice).
    Активирует Premium подписку после успешной оплаты.
    """
    user_id = message.from_user.id
    payment = message.successful_payment
    
    logger.info(f"Успешная оплата от user_id={user_id}, payment_info={payment}")
    
    try:
        invoice_payload = payment.invoice_payload
        total_amount = payment.total_amount / 100  # Сумма в рублях (Telegram передает в копейках)
        
        logger.info(f"Обработка успешной оплаты: user_id={user_id}, amount={total_amount} RUB, payload={invoice_payload}")
        
        # Активируем Premium подписку на 30 дней
        success = await activate_premium_subscription(user_id, duration_days=30)
        
        if success:
            logger.info(f"Premium подписка успешно активирована для user_id={user_id} после успешной оплаты")
            
            await message.answer(
                "✨ <b>Спасибо за покупку!</b> ✨\n\n"
                "Ваша Premium подписка на 30 дней активирована.\n\n"
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
            logger.error(f"Ошибка при активации Premium подписки для user_id={user_id} после успешной оплаты")
            await message.answer(
                "❌ Произошла ошибка при активации Premium подписки.\n\n"
                "Пожалуйста, обратитесь в поддержку: /support\n\n"
                "Приложите эту информацию:\n"
                f"Payment ID: {invoice_payload}"
            )
            
    except Exception as e:
        logger.error(f"Ошибка в successful_payment_handler для user_id={user_id}: {e}", exc_info=True)
        await message.answer(
            "❌ Произошла ошибка при обработке оплаты.\n\n"
            "Пожалуйста, обратитесь в поддержку: /support"
        )


async def check_and_activate_payment(user_id: int, payment_id: str) -> bool:
    """
    Проверяет статус платежа и активирует Premium подписку, если оплата успешна.
    
    Args:
        user_id: ID пользователя
        payment_id: ID платежа в ЮKassa
        
    Returns:
        bool: True если платеж успешен и подписка активирована
    """
    logger.info(f"Проверка и активация платежа: user_id={user_id}, payment_id={payment_id}")
    
    try:
        user_data = get_user(user_id)
        pending_payments = user_data.get('pending_payments', {})
        
        if payment_id not in pending_payments:
            logger.warning(f"Платеж payment_id={payment_id} не найден в pending_payments для user_id={user_id}")
            return False
        
        payment_info = pending_payments[payment_id]
        
        if payment_info.get('status') != 'pending':
            logger.info(f"Платеж payment_id={payment_id} уже обработан для user_id={user_id}")
            return payment_info.get('status') == 'completed'
        
        # Проверяем статус платежа в ЮKassa
        is_paid = await is_payment_successful(payment_id)
        
        if is_paid:
            logger.info(f"Платеж payment_id={payment_id} успешно оплачен, активируем Premium для user_id={user_id}")
            
            # Активируем Premium подписку на 30 дней
            success = await activate_premium_subscription(user_id, duration_days=30)
            
            if success:
                payment_info['status'] = 'completed'
                payment_info['completed_at'] = datetime.now().isoformat()
                logger.info(f"Premium подписка активирована для user_id={user_id} после оплаты payment_id={payment_id}")
                return True
            else:
                logger.error(f"Ошибка при активации Premium для user_id={user_id} после оплаты payment_id={payment_id}")
                return False
        else:
            logger.info(f"Платеж payment_id={payment_id} еще не оплачен для user_id={user_id}")
            return False
            
    except Exception as e:
        logger.error(f"Ошибка при проверке и активации платежа payment_id={payment_id} для user_id={user_id}: {e}", exc_info=True)
        return False
