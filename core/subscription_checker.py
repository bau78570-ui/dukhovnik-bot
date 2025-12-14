import os
import logging
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
    user_data['status'] = 'free'
    # TODO: Сохранить user_db в постоянное хранилище
    return True

async def is_subscription_active(user_id: int) -> bool:
    """
    Проверяет активность платной подписки пользователя.
    Проверяет наличие и валидность subscription_end_date в базе данных пользователя.
    Также проверяет пробный период: если trial_start_date + 3 days < datetime.now() и status == 'free' → возвращает False.
    """
    user_data = get_user(user_id)
    
    # Проверка пробного периода: если истёк и status == 'free', отключаем доступ
    trial_start_date = user_data.get('trial_start_date')
    status = user_data.get('status')
    
    if trial_start_date and status == 'free':
        if isinstance(trial_start_date, str):
            try:
                trial_start_date = datetime.fromisoformat(trial_start_date)
            except (ValueError, TypeError):
                pass
        
        if isinstance(trial_start_date, datetime):
            trial_end_date = trial_start_date + timedelta(days=TRIAL_DURATION_DAYS)
            if datetime.now() >= trial_end_date:
                # Пробный период истёк
                user_data['status'] = 'expired'
                logging.info(f"Пробный период истёк для user_id {user_id}")
                return False
    
    subscription_end = user_data.get('subscription_end_date')
    if subscription_end:
        # Если subscription_end_date - это datetime, проверяем, не истекла ли подписка
        if isinstance(subscription_end, datetime):
            return datetime.now() < subscription_end
        # Если это строка, пытаемся распарсить
        elif isinstance(subscription_end, str):
            try:
                end_date = datetime.fromisoformat(subscription_end)
                return datetime.now() < end_date
            except (ValueError, TypeError):
                return False
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

        # Команды, которые должны работать без проверки доступа
        allowed_commands = ['/start', '/subscribe', '/support', '/documents', '/admin']
        
        # Проверяем, является ли это командой, которую нужно пропустить
        if isinstance(event, Message) and event.text:
            # Извлекаем команду из текста (учитываем формат /command или /command@botname)
            command_text = event.text.split()[0].split('@')[0] if event.text else ""
            if command_text in allowed_commands:
                print(f"INFO: Command {command_text} is allowed without access check. Access GRANTED.")
                print("--- Access Check Finished ---\n")
                return await handler(event, data)

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
            print("INFO: Subscription is not active. Proceeding to check for trial activation.")
        
        # Шаг 4: Автоматическая активация пробного периода для новых пользователей
        user_data = get_user(user_id)
        trial_start = user_data.get('trial_start_date')
        
        if trial_start is None:
            # Пробный период еще не был активирован - активируем его автоматически
            print("INFO: Trial period has never been activated. Activating trial automatically...")
            await activate_trial(user_id)
            print(f"RESULT: Trial period activated automatically. Access GRANTED for {TRIAL_DURATION_DAYS} days.")
            print("--- Access Check Finished ---\n")
            return await handler(event, data)
        else:
            # Пробный период был активирован ранее, но истек
            print("RESULT: Trial period was activated previously but has expired. Access DENIED.")
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
