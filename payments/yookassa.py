"""
Модуль для работы с ЮKassa API.
Создание платежей и проверка их статуса.
"""
import os
import logging
from datetime import datetime, timedelta
from yookassa import Configuration, Payment
from yookassa.domain.notification import WebhookNotificationFactory
from yookassa.domain.models.currency import Currency
from yookassa.domain.models.receipt import Receipt, ReceiptItem, PaymentMode, PaymentSubject
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

logger = logging.getLogger(__name__)


async def create_premium_payment(user_id: int, description: str = "Premium подписка на 30 дней") -> dict:
    """
    Создает платеж для Premium подписки на 30 дней (299 ₽).
    
    Args:
        user_id: ID пользователя Telegram
        description: Описание платежа
        
    Returns:
        dict: Словарь с информацией о платеже (payment_id, confirmation_url, status)
    """
    try:
        logger.info(f"Создание платежа для user_id={user_id}, цена={PREMIUM_PRICE} ₽")
        
        # Создаем платеж через ЮKassa API
        payment_data = {
            "amount": {
                "value": f"{PREMIUM_PRICE:.2f}",
                "currency": Currency.RUB
            },
            "confirmation": {
                "type": "redirect",
                "return_url": "https://t.me/dukhovnik_bot"  # URL для возврата после оплаты
            },
            "capture": True,
            "description": description,
            "metadata": {
                "user_id": str(user_id),
                "subscription_type": "premium_30_days",
                "subscription_duration_days": str(PREMIUM_DURATION_DAYS)
            },
            "test": YOOKASSA_TEST
        }
        
        logger.info(f"Отправка запроса на создание платежа в ЮKassa (тестовый режим: {YOOKASSA_TEST})")
        payment = Payment.create(payment_data, idempotency_key=f"premium_{user_id}_{int(datetime.now().timestamp())}")
        
        payment_id = payment.id
        confirmation_url = payment.confirmation.confirmation_url
        status = payment.status
        
        logger.info(f"Платеж создан успешно: payment_id={payment_id}, status={status}, confirmation_url={confirmation_url[:50]}...")
        
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
