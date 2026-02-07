# -*- coding: utf-8 -*-
"""
Модуль для интеграции с Яндекс.Метрикой через HTTP API.
Отправляет события из Telegram бота в Яндекс.Метрику для аналитики.
Поддерживает оффлайн-конверсии через Management API.
"""

import aiohttp
import asyncio
import logging
import os
from typing import Optional
from datetime import datetime
import hashlib
import uuid
from dotenv import load_dotenv

load_dotenv()

# Номер счётчика Яндекс.Метрики
YANDEX_METRIKA_COUNTER_ID = "106602878"

# URL для отправки событий в Яндекс.Метрику
YANDEX_METRIKA_URL = "https://mc.yandex.ru/watch/{counter_id}"

# URL для отправки оффлайн-конверсий
YANDEX_METRIKA_OFFLINE_URL = f"https://api-metrika.yandex.net/management/v1/counter/{YANDEX_METRIKA_COUNTER_ID}/offline_conversions/upload"

# Токен для Management API
YANDEX_METRIKA_TOKEN = os.getenv("YANDEX_METRIKA_TOKEN", "")

# ID целей в Яндекс.Метрике
GOAL_BOT_START = "508977279"
GOAL_FREE_PERIOD_START = "508976625"
GOAL_PREMIUM_PAYMENT = "508976841"

logger = logging.getLogger(__name__)


def generate_client_id(user_id: int) -> str:
    """
    Генерирует уникальный Client ID для пользователя на основе его Telegram ID.
    Яндекс.Метрика требует ClientID для идентификации пользователей.
    """
    # Создаем стабильный ClientID из user_id
    return str(user_id)


async def send_metrika_event(
    event_name: str,
    user_id: int,
    params: Optional[dict] = None
) -> bool:
    """
    Отправляет событие в Яндекс.Метрику через HTTP API.
    
    :param event_name: Название события (например, 'bot_start', 'subscription_purchased')
    :param user_id: Telegram ID пользователя
    :param params: Дополнительные параметры события
    :return: True если событие отправлено успешно, False в противном случае
    """
    try:
        client_id = generate_client_id(user_id)
        
        # Параметры запроса для Яндекс.Метрики
        url = f"https://mc.yandex.ru/watch/{YANDEX_METRIKA_COUNTER_ID}"
        
        # Формируем параметры запроса
        query_params = {
            'browser-info': f'pa:1:ar:1:pv:1:v:{client_id}',
            'page-url': f'https://t.me/dukhovnik_bot?user_id={user_id}',
            'page-ref': 'https://t.me/dukhovnik_bot',
            'rn': str(uuid.uuid4().int)[:16],  # Случайное число для избежания кеширования
        }
        
        # Добавляем параметры события
        if params:
            query_params['event-params'] = str(params)
        
        # Отправляем reach goal (достижение цели)
        reach_goal_params = query_params.copy()
        reach_goal_params['page-url'] += f'&ym_goal={event_name}'
        
        timeout = aiohttp.ClientTimeout(total=5)  # Таймаут 5 секунд
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, params=reach_goal_params) as response:
                if response.status == 200:
                    logger.info(f"Яндекс.Метрика: событие '{event_name}' отправлено для user_id={user_id}")
                    return True
                else:
                    logger.warning(f"Яндекс.Метрика: ошибка {response.status} при отправке события '{event_name}'")
                    return False
                    
    except (asyncio.TimeoutError, aiohttp.ServerTimeoutError, aiohttp.ClientConnectionError) as e:
        # ВАЖНО: Ловим таймауты ПЕРВЫМИ (до общего Exception)
        logger.warning(f"Яндекс.Метрика: таймаут при отправке события '{event_name}' для user_id={user_id}: {e}")
        return False
    except aiohttp.ClientError as e:
        logger.warning(f"Яндекс.Метрика: сетевая ошибка при отправке события '{event_name}': {e}")
        return False
    except Exception as e:
        logger.error(f"Яндекс.Метрика: неизвестная ошибка при отправке события '{event_name}': {e}")
        return False


async def track_bot_start(user_id: int, is_new_user: bool = False):
    """Трекинг события запуска бота."""
    await send_metrika_event(
        'bot_start',
        user_id,
        {'is_new_user': is_new_user}
    )


async def track_new_user(user_id: int, utm_source: str = None):
    """Трекинг регистрации нового пользователя."""
    params = {}
    if utm_source:
        params['utm_source'] = utm_source
    
    await send_metrika_event('new_user_registered', user_id, params)


async def track_subscription_activated(user_id: int, subscription_type: str, amount: int = None):
    """Трекинг активации подписки."""
    params = {'subscription_type': subscription_type}
    if amount:
        params['amount'] = amount
    
    await send_metrika_event('subscription_activated', user_id, params)


async def track_payment_success(user_id: int, amount: int, duration_days: int):
    """Трекинг успешного платежа."""
    await send_metrika_event(
        'payment_success',
        user_id,
        {'amount': amount, 'duration_days': duration_days}
    )


async def track_feature_used(user_id: int, feature_name: str):
    """Трекинг использования функций бота."""
    await send_metrika_event(
        f'feature_used_{feature_name}',
        user_id,
        {'feature': feature_name}
    )


async def track_free_period_activated(user_id: int):
    """Трекинг активации бесплатного периода."""
    await send_metrika_event('free_period_activated', user_id)


async def track_trial_activated(user_id: int):
    """Трекинг активации пробного периода."""
    await send_metrika_event('trial_activated', user_id)


# ===== OFFLINE CONVERSIONS API =====

async def send_offline_conversion(
    user_id: int,
    goal_id: str,
    price: float = 0.0,
    currency: str = "RUB"
) -> bool:
    """
    Отправляет оффлайн-конверсию в Яндекс.Метрику через Management API.
    
    :param user_id: Telegram ID пользователя (используется как ClientID)
    :param goal_id: ID цели в Яндекс.Метрике
    :param price: Стоимость конверсии (в рублях)
    :param currency: Валюта (по умолчанию RUB)
    :return: True если конверсия отправлена успешно, False в противном случае
    """
    if not YANDEX_METRIKA_TOKEN:
        logger.warning("Яндекс.Метрика: токен не настроен, оффлайн-конверсия не отправлена")
        return False
    
    try:
        client_id = generate_client_id(user_id)
        
        # Текущее время в UNIX timestamp
        current_timestamp = int(datetime.now().timestamp())
        
        # Формируем данные конверсии
        conversion_data = {
            "conversions": [
                {
                    "ClientID": client_id,
                    "Target": goal_id,
                    "DateTime": current_timestamp,
                    "Price": price,
                    "Currency": currency
                }
            ]
        }
        
        headers = {
            "Authorization": f"OAuth {YANDEX_METRIKA_TOKEN}",
            "Content-Type": "application/json"
        }
        
        timeout = aiohttp.ClientTimeout(total=10)  # Таймаут 10 секунд
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(YANDEX_METRIKA_OFFLINE_URL, json=conversion_data, headers=headers) as response:
                response_text = await response.text()
                
                if response.status in [200, 201, 202]:
                    logger.info(f"Оффлайн-конверсия {goal_id} отправлена для user_id={user_id}, price={price} {currency}")
                    return True
                else:
                    logger.warning(f"Яндекс.Метрика: ошибка {response.status} при отправке оффлайн-конверсии {goal_id}: {response_text}")
                    return False
                    
    except (asyncio.TimeoutError, aiohttp.ServerTimeoutError, aiohttp.ClientConnectionError) as e:
        logger.warning(f"Яндекс.Метрика: таймаут при отправке оффлайн-конверсии {goal_id} для user_id={user_id}: {e}")
        return False
    except aiohttp.ClientError as e:
        logger.warning(f"Яндекс.Метрика: сетевая ошибка при отправке оффлайн-конверсии {goal_id}: {e}")
        return False
    except Exception as e:
        logger.error(f"Яндекс.Метрика: ошибка при отправке оффлайн-конверсии {goal_id}: {e}")
        return False


async def send_offline_conversion_bot_start(user_id: int):
    """
    Отправляет оффлайн-конверсию для цели 'bot_start' (первый запуск бота).
    Goal ID: 508977279
    """
    return await send_offline_conversion(user_id, GOAL_BOT_START, price=0.0, currency="RUB")


async def send_offline_conversion_free_period(user_id: int):
    """
    Отправляет оффлайн-конверсию для цели 'free_period_start' (активация бесплатного периода).
    Goal ID: 508976625
    """
    return await send_offline_conversion(user_id, GOAL_FREE_PERIOD_START, price=0.0, currency="RUB")


async def send_offline_conversion_payment(user_id: int, amount_kopecks: int):
    """
    Отправляет оффлайн-конверсию для цели 'premium_payment' (успешная оплата).
    Goal ID: 508976841
    
    :param user_id: Telegram ID пользователя
    :param amount_kopecks: Сумма платежа в копейках (приходит от Telegram Payments)
    """
    # Конвертируем копейки в рубли
    amount_rubles = amount_kopecks / 100.0
    return await send_offline_conversion(user_id, GOAL_PREMIUM_PAYMENT, price=amount_rubles, currency="RUB")
