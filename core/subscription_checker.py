import os
from dotenv import load_dotenv
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from datetime import datetime, timedelta
from core.user_database import user_db, get_user # Импортируем user_db и get_user

load_dotenv()

ADMIN_ID = os.getenv("ADMIN_ID", "")
TRIAL_DURATION_DAYS = 3

# --- Функции проверки статусов ---
async def is_trial_active(user_id: int) -> bool:
    """
    Проверяет активность пробного периода пользователя.
    """
    user_data = get_user(user_id)
    trial_start = user_data.get('trial_start_date')
    if trial_start:
        return datetime.now() < (trial_start + timedelta(days=TRIAL_DURATION_DAYS))
    return False

async def activate_trial(user_id: int) -> bool:
    """
    Активирует пробный период для пользователя, если он еще не был активирован.
    Возвращает True, если пробный период активирован или уже активен, False в противном случае.
    """
    user_data = get_user(user_id)
    if user_data.get('trial_start_date'):
        # Пробный период уже был активирован
        return await is_trial_active(user_id)
    
    user_data['trial_start_date'] = datetime.now()
    # TODO: Сохранить user_db в постоянное хранилище
    return True

async def is_subscription_active(user_id: int) -> bool:
    """
    Имитирует проверку активности платной подписки пользователя.
    TODO: Заменить на реальную логику проверки в базе данных.
    """
    return False

async def is_premium(user_id: int) -> bool:
    """
    Проверяет, имеет ли пользователь Premium-доступ (активный пробный период или подписка).
    """
    return await is_trial_active(user_id) or await is_subscription_active(user_id)

class AccessCheckerMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        user_id = event.from_user.id
        print("\n--- Access Check Started ---")
        print(f"User ID: {user_id}, Admin ID from .env: {ADMIN_ID}")

        # Шаг 1: Проверка на Администратора
        if str(user_id) == str(ADMIN_ID):
            print("RESULT: User is ADMIN. Access GRANTED.")
            print("--- Access Check Finished ---\n")
            return await handler(event, data)
        else:
            print("INFO: User is not Admin. Proceeding to next checks.")

        # Шаг 2: Проверка на пробный период
        is_trial = await is_trial_active(user_id)
        print(f"INFO: Checking trial status... Result: {is_trial}")
        if is_trial:
            print("RESULT: Trial is active. Access GRANTED.")
            print("--- Access Check Finished ---\n")
            return await handler(event, data)
        else:
            print("INFO: Trial is not active. Proceeding to next checks.")

        # Шаг 3: Проверка на платную подписку
        is_subscribed = await is_subscription_active(user_id)
        print(f"INFO: Checking subscription status... Result: {is_subscribed}")
        if is_subscribed:
            print("RESULT: Subscription is active. Access GRANTED.")
            print("--- Access Check Finished ---\n")
            return await handler(event, data)
        else:
            print("INFO: Subscription is not active. Proceeding to deny access.")
        
        # Шаг 4: Отказ в доступе
        print("RESULT: No access rights found. Access DENIED.")
        print("--- Access Check Finished ---\n")
        no_access_text = (
            "✨ <b>Эта функция — часть Premium-доступа.</b>\n\n"
            "Она открывает безграничное общение с AI-Собеседником и доступ к эксклюзивным материалам для вашего духовного роста.\n\n"
            "Позвольте себе этот дар! Нажмите /subscribe, чтобы присоединиться."
        )
        if isinstance(event, Message):
            await event.answer(no_access_text, parse_mode='HTML')
        elif isinstance(event, CallbackQuery):
            await event.message.answer(no_access_text, parse_mode='HTML')
        return

# Главный декоратор (middleware)
check_access = AccessCheckerMiddleware()
