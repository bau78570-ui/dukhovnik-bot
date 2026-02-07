# -*- coding: utf-8 -*-
"""
Модуль для интеграции с Яндекс.Метрикой через HTTP API.
Отправляет события из Telegram бота в Яндекс.Метрику для аналитики.
"""

import aiohttp
import asyncio
import logging
from typing import Optional
import hashlib
import uuid

# Номер счётчика Яндекс.Метрики
YANDEX_METRIKA_COUNTER_ID = "106602878"

# URL для отправки событий в Яндекс.Метрику
YANDEX_METRIKA_URL = "https://mc.yandex.ru/watch/{counter_id}"

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
