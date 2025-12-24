"""
Модуль для работы с ЮKassa API.
Создание платежей и проверка их статуса.
"""
import os
import logging
from datetime import datetime, timedelta
from yookassa import Configuration, Payment
from dotenv import load_dotenv

load_dotenv()

# Настройка ЮKassa
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY")
YOOKASSA_TEST = os.getenv("YOOKASSA_TEST", "False").lower() == "true"

# Инициализация конфигурации ЮKassa
Configuration.account_id = YOOKASSA_SHOP_ID
Configuration.secret_key = YOOKASSA_SECRET_KEY

PREMIUM_PRICE = 299.00  # Цена в рублях
PREMIUM_DURATION_DAYS = 30  # Длительность подписки в днях

# Тестовая карта для тестового режима ЮKassa: 5555 5555 5555 4444
# Срок действия: любая будущая дата (например, 12/25)
# CVV: любые 3 цифры (например, 123)

logger = logging.getLogger(__name__)


async def create_premium_payment(user_id: int, description: str = "Premium подписка на 30 дней") -> dict:
    """
    Создает платеж для Premium подписки на 30 дней (299 ₽).
    Проверяет существующие pending платежи перед созданием нового для предотвращения дублирования.
    
    Args:
        user_id: ID пользователя Telegram
        description: Описание платежа
        
    Returns:
        dict: Словарь с информацией о платеже (payment_id, confirmation_url, status)
    """
    try:
        logger.info(f"Создание платежа для user_id={user_id}, цена={PREMIUM_PRICE} ₽")
        
        # Проверяем существующие pending платежи пользователя
        from core.user_database import get_user
        user_data = get_user(user_id)
        pending_payments = user_data.get('pending_payments', {})
        
        # Очищаем старые pending платежи со ссылками на paywall.tg
        payments_to_remove = []
        for existing_payment_id, payment_info in pending_payments.items():
            if payment_info.get('status') == 'pending':
                try:
                    # Проверяем статус существующего платежа в ЮKassa
                    payment_status = await check_payment_status(existing_payment_id)
                    status = payment_status.get("status", "")
                    paid = payment_status.get("paid", False)
                    
                    if paid or status == "succeeded":
                        # Платеж уже оплачен, удаляем из pending
                        logger.info(f"Платеж {existing_payment_id} уже оплачен, удаляем из pending")
                        payments_to_remove.append(existing_payment_id)
                    elif status == "pending" and not paid:
                        # Проверяем ссылку платежа
                        try:
                            payment = Payment.find_one(existing_payment_id)
                            confirmation_url = payment.confirmation.confirmation_url
                            
                            # Если ссылка ведет на paywall.tg, удаляем такой платеж
                            if confirmation_url and "paywall.tg" in confirmation_url:
                                logger.info(
                                    f"Найден pending платеж со ссылкой на paywall.tg: payment_id={existing_payment_id}, "
                                    f"удаляем из pending и создадим новый"
                                )
                                payments_to_remove.append(existing_payment_id)
                            # Если ссылка валидная, используем этот платеж
                            elif confirmation_url and "paywall.tg" not in confirmation_url:
                                logger.info(
                                    f"Используется существующий pending платеж: payment_id={existing_payment_id}, "
                                    f"confirmation_url={confirmation_url}"
                                )
                                return {
                                    "payment_id": existing_payment_id,
                                    "confirmation_url": confirmation_url,
                                    "status": status,
                                    "amount": PREMIUM_PRICE,
                                    "currency": "RUB"
                                }
                        except Exception as e:
                            logger.warning(f"Не удалось получить данные существующего платежа {existing_payment_id}: {e}")
                except Exception as e:
                    logger.warning(f"Ошибка при проверке существующего платежа {existing_payment_id}: {e}")
        
        # Удаляем помеченные платежи
        for payment_id_to_remove in payments_to_remove:
            if payment_id_to_remove in pending_payments:
                del pending_payments[payment_id_to_remove]
        
        # Создаем новый платеж через ЮKassa API
        metadata = {
            "user_id": str(user_id),
            "subscription_type": "premium_30_days",
            "subscription_duration_days": str(PREMIUM_DURATION_DAYS)
        }
        
        logger.info(
            f"Отправка запроса на создание платежа в ЮKassa (тестовый режим: {YOOKASSA_TEST}). "
            f"Параметры: confirmation.type=redirect, return_url=https://t.me/dukhovnik_bot"
        )
        # Используем детерминированный idempotency_key для предотвращения дублирования платежей
        # При повторных вызовах с тем же ключом ЮKassa вернет существующий платеж
        idempotency_key = f"premium_{user_id}_subscription"
        payment = Payment.create({
            "amount": {"value": f"{PREMIUM_PRICE:.2f}", "currency": "RUB"},
            "confirmation": {"type": "redirect", "return_url": "https://t.me/dukhovnik_bot"},
            "capture": True,
            "description": description,
            "metadata": metadata
        }, idempotency_key=idempotency_key)
        
        payment_id = payment.id
        confirmation_url = payment.confirmation.confirmation_url
        status = payment.status
        
        # Проверяем, что полученная ссылка не ведет на paywall.tg
        # Если ведет, создаем новый платеж с другим ключом
        if confirmation_url and "paywall.tg" in confirmation_url:
            logger.warning(
                f"Получен платеж с ссылкой на paywall.tg: payment_id={payment_id}, "
                f"создаем новый платеж с другим idempotency_key"
            )
            # Создаем новый платеж с другим ключом, добавляя timestamp
            from datetime import datetime
            idempotency_key = f"premium_{user_id}_subscription_{int(datetime.now().timestamp())}"
            payment = Payment.create({
                "amount": {"value": f"{PREMIUM_PRICE:.2f}", "currency": "RUB"},
                "confirmation": {"type": "redirect", "return_url": "https://t.me/dukhovnik_bot"},
                "capture": True,
                "description": description,
                "metadata": metadata
            }, idempotency_key=idempotency_key)
            payment_id = payment.id
            confirmation_url = payment.confirmation.confirmation_url
            status = payment.status
            
            # Если и новый платеж имеет ссылку на paywall.tg, логируем ошибку
            if confirmation_url and "paywall.tg" in confirmation_url:
                logger.error(
                    f"КРИТИЧЕСКАЯ ОШИБКА: Новый платеж также имеет ссылку на paywall.tg: "
                    f"payment_id={payment_id}, confirmation_url={confirmation_url}"
                )
        
        # Финальная проверка ссылки перед возвратом
        if confirmation_url and "paywall.tg" in confirmation_url:
            logger.error(
                f"КРИТИЧЕСКАЯ ОШИБКА: Финальный платеж все еще имеет ссылку на paywall.tg: "
                f"payment_id={payment_id}, confirmation_url={confirmation_url}. "
                f"Возможно, проблема в настройках ЮKassa или требуется проверка параметров платежа."
            )
            # Все равно возвращаем, но с предупреждением в логах
        else:
            logger.info(
                f"Платеж создан успешно с валидной ссылкой: payment_id={payment_id}, "
                f"status={status}, confirmation_type={payment.confirmation.type}, "
                f"confirmation_url={confirmation_url[:100]}..."
            )
        
        return {
            "payment_id": payment_id,
            "confirmation_url": confirmation_url,
            "status": status,
            "amount": PREMIUM_PRICE,
            "currency": "RUB"
        }
        
    except Exception as e:
        logger.error(f"Ошибка при создании платежа для user_id={user_id}: {e}", exc_info=True)
        raise


async def check_payment_status(payment_id: str) -> dict:
    """
    Проверяет статус платежа по payment_id.
    
    Args:
        payment_id: ID платежа в ЮKassa
        
    Returns:
        dict: Словарь с информацией о статусе платежа (status, paid, metadata)
    """
    try:
        logger.info(f"Проверка статуса платежа: payment_id={payment_id}")
        
        payment = Payment.find_one(payment_id)
        
        status = payment.status
        paid = payment.paid
        metadata = payment.metadata
        
        logger.info(f"Статус платежа payment_id={payment_id}: status={status}, paid={paid}")
        
        return {
            "payment_id": payment_id,
            "status": status,
            "paid": paid,
            "metadata": metadata,
            "amount": float(payment.amount.value) if hasattr(payment.amount, 'value') else None,
            "currency": payment.amount.currency if hasattr(payment.amount, 'currency') else None
        }
        
    except Exception as e:
        logger.error(f"Ошибка при проверке статуса платежа payment_id={payment_id}: {e}", exc_info=True)
        raise


async def is_payment_successful(payment_id: str) -> bool:
    """
    Проверяет, успешно ли оплачен платеж.
    
    Args:
        payment_id: ID платежа в ЮKassa
        
    Returns:
        bool: True если платеж успешно оплачен, False в противном случае
    """
    try:
        payment_status = await check_payment_status(payment_id)
        is_paid = payment_status.get("paid", False)
        status = payment_status.get("status", "")
        
        logger.info(f"Проверка успешности платежа payment_id={payment_id}: paid={is_paid}, status={status}")
        
        # Платеж считается успешным, если он оплачен или находится в статусе succeeded
        return is_paid or status == "succeeded"
        
    except Exception as e:
        logger.error(f"Ошибка при проверке успешности платежа payment_id={payment_id}: {e}", exc_info=True)
        return False


def parse_webhook_notification(request_body: dict) -> dict:
    """
    Парсит webhook уведомление от ЮKassa.
    
    Args:
        request_body: Тело запроса от webhook
        
    Returns:
        dict: Распарсенные данные уведомления
    """
    try:
        logger.info(f"Парсинг webhook уведомления от ЮKassa")
        
        # Ленивый импорт, чтобы избежать проблем при загрузке модуля, если webhook не используется
        from yookassa.domain.notification import WebhookNotificationFactory  # type: ignore
        notification = WebhookNotificationFactory().create(request_body)
        payment_response = notification.object
        
        payment_id = payment_response.id
        status = payment_response.status
        paid = payment_response.paid
        metadata = payment_response.metadata
        
        logger.info(f"Webhook обработан: payment_id={payment_id}, status={status}, paid={paid}")
        
        return {
            "payment_id": payment_id,
            "status": status,
            "paid": paid,
            "metadata": metadata,
            "event": notification.event
        }
        
    except Exception as e:
        logger.error(f"Ошибка при парсинге webhook уведомления: {e}", exc_info=True)
        raise
