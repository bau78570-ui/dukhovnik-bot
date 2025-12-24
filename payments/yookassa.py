"""
Модуль для работы с ЮKassa API.
Используется для проверки статуса платежей, созданных вне Telegram Payments.
"""
import logging
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Токены ЮKassa API (для прямых платежей, не через Telegram Payments)
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID", "")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY", "")


async def check_payment_status(payment_id: str) -> Optional[dict]:
    """
    Проверяет статус платежа в ЮKassa.
    
    Args:
        payment_id: ID платежа в ЮKassa
        
    Returns:
        dict: Информация о платеже или None в случае ошибки
    """
    # TODO: Реализовать проверку статуса через ЮKassa API
    # Это используется для платежей, созданных вне Telegram Payments
    logger.warning(f"check_payment_status не реализован для payment_id={payment_id}")
    return None


async def is_payment_successful(payment_id: str) -> bool:
    """
    Проверяет, успешно ли оплачен платеж в ЮKassa.
    
    Args:
        payment_id: ID платежа в ЮKassa
        
    Returns:
        bool: True если платеж успешен, False в противном случае
    """
    # TODO: Реализовать проверку статуса через ЮKassa API
    # Это используется для платежей, созданных вне Telegram Payments
    logger.warning(f"is_payment_successful не реализован для payment_id={payment_id}")
    return False

