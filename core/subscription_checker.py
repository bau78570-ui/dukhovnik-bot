import os
import logging
from dotenv import load_dotenv
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from datetime import datetime, timedelta
from core.user_database import user_db, get_user, save_user_db # Импортируем user_db, get_user и save_user_db
from handlers.support_handler import SupportState # Импортируем состояние поддержки
from states import PrayerState # Импортируем состояние молитвы

load_dotenv()

ADMIN_ID = os.getenv("ADMIN_ID", "")
TRIAL_DURATION_DAYS = 3

# --- Функции проверки статусов ---
async def is_trial_active(user_id: int) -> bool:
    """
    Проверяет активность пробного периода пользователя.
    Обрабатывает как datetime, так и строковый формат (ISO) trial_start_date.
    """
    user_data = get_user(user_id)
    trial_start = user_data.get('trial_start_date')
    if trial_start:
        # Обрабатываем случай, когда trial_start_date хранится как строка
        if isinstance(trial_start, str):
            try:
                trial_start = datetime.fromisoformat(trial_start)
            except (ValueError, TypeError):
                logging.warning(f"Не удалось распарсить trial_start_date для user_id={user_id}: {trial_start}")
                return False
        
        # Проверяем, что trial_start является datetime объектом
        if isinstance(trial_start, datetime):
            trial_end_date = trial_start + timedelta(days=TRIAL_DURATION_DAYS)
            return datetime.now() < trial_end_date
    
    return False

async def activate_trial(user_id: int) -> bool:
    """
    Активирует пробный период для пользователя, если он еще не был активирован.
    Возвращает True, если пробный период активирован или уже активен, False в противном случае.
    НЕ активирует повторно, если пробный период уже был активирован ранее (даже если истек).
    """
    user_data = get_user(user_id)
    trial_start = user_data.get('trial_start_date')
    
    if trial_start is not None:
        # Пробный период уже был активирован - проверяем, активен ли он еще
        is_active = await is_trial_active(user_id)
        if not is_active:
            # Пробный период истек - убеждаемся, что статус установлен правильно
            if user_data.get('status') == 'free':
                user_data['status'] = 'expired'
                save_user_db()  # Сохраняем изменения
                logging.info(f"Пробный период истек для user_id={user_id}, статус установлен на 'expired'")
        return is_active
    
    # Пробный период еще не был активирован - активируем его
    user_data['trial_start_date'] = datetime.now()
    user_data['status'] = 'free'
    save_user_db()  # Сохраняем изменения
    logging.info(f"Пробный период активирован для user_id={user_id} на {TRIAL_DURATION_DAYS} дней")
    return True

async def activate_premium_subscription(user_id: int, duration_days: int = 30) -> bool:
    """
    Активирует Premium подписку для пользователя на указанное количество дней.
    
    Args:
        user_id: ID пользователя
        duration_days: Количество дней подписки (по умолчанию 30)
        
    Returns:
        bool: True если подписка активирована успешно
    """
    logging.info(f"Активация Premium подписки для user_id={user_id}, duration_days={duration_days}")
    
    try:
        user_data = get_user(user_id)
        subscription_end_date = datetime.now() + timedelta(days=duration_days)
        
        # Если подписка уже активна, продлеваем её от текущей даты окончания
        current_end = user_data.get('subscription_end_date')
        if current_end:
            if isinstance(current_end, datetime):
                if current_end > datetime.now():
                    # Подписка еще активна, продлеваем от даты окончания
                    subscription_end_date = current_end + timedelta(days=duration_days)
                    logging.info(f"Продление активной подписки для user_id={user_id}, новый срок до {subscription_end_date}")
                else:
                    # Подписка истекла, начинаем новую от текущей даты
                    logging.info(f"Начало новой подписки для user_id={user_id}, срок до {subscription_end_date}")
            elif isinstance(current_end, str):
                try:
                    current_end_dt = datetime.fromisoformat(current_end)
                    if current_end_dt > datetime.now():
                        subscription_end_date = current_end_dt + timedelta(days=duration_days)
                        logging.info(f"Продление активной подписки (из строки) для user_id={user_id}, новый срок до {subscription_end_date}")
                except (ValueError, TypeError):
                    logging.info(f"Начало новой подписки для user_id={user_id}, срок до {subscription_end_date}")
        
        user_data['subscription_end_date'] = subscription_end_date
        user_data['status'] = 'premium'
        save_user_db()  # Сохраняем изменения
        logging.info(f"Premium подписка успешно активирована для user_id={user_id}, срок действия до {subscription_end_date}")
        return True
        
    except Exception as e:
        logging.error(f"Ошибка при активации Premium подписки для user_id={user_id}: {e}", exc_info=True)
        return False

async def is_subscription_active(user_id: int) -> bool:
    """
    Проверяет активность платной подписки пользователя.
    Проверяет наличие и валидность subscription_end_date в базе данных пользователя.
    
    ВАЖНО: Эта функция проверяет ТОЛЬКО платные подписки, не пробные периоды.
    Для проверки пробного периода используйте функцию is_trial_active().
    
    Returns:
        bool: True если у пользователя есть активная платная подписка, False в противном случае
    """
    user_data = get_user(user_id)
    
    # Проверяем платную подписку
    subscription_end = user_data.get('subscription_end_date')
    if subscription_end:
        # Если subscription_end_date - это datetime, проверяем, не истекла ли подписка
        if isinstance(subscription_end, datetime):
            if datetime.now() < subscription_end:
                # Платная подписка активна
                return True
        # Если это строка, пытаемся распарсить
        elif isinstance(subscription_end, str):
            try:
                end_date = datetime.fromisoformat(subscription_end)
                if datetime.now() < end_date:
                    # Платная подписка активна
                    return True
            except (ValueError, TypeError):
                pass
    
    # Если платной подписки нет или она истекла, возвращаем False
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
        # Разрешаем служебные сообщения Telegram Payments без проверки подписки
        if isinstance(event, Message):
            if getattr(event, "successful_payment", None) or getattr(event, "recurring_payment", None):
                logging.info("INFO: Payment message detected. Access GRANTED.")
                return await handler(event, data)

        user_id = event.from_user.id
        print("\n--- Access Check Started ---")
        print(f"User ID: {user_id}, Admin ID from .env: {ADMIN_ID}")

        # Команды, которые должны работать без проверки доступа (всегда доступны)
        allowed_commands = ['/start', '/subscribe', '/support', '/documents', '/favorites', '/settings', '/admin', '/check_payment', '/check_payment_config']
        
        # Callback-запросы, которые должны работать без проверки доступа (всегда доступны)
        allowed_callbacks = [
            'start_trial',  # Активация пробного периода
            'subscribe_premium',  # Кнопка оформления подписки
            'subscribe_1month', 'subscribe_3month', 'subscribe_12month',  # Выбор тарифа
            'open_docs',  # Открытие документов
        ]
        # Callback-запросы, которые начинаются с этих префиксов (всегда доступны)
        allowed_callback_prefixes = [
            'toggle_',  # Настройки уведомлений
            'fav_',  # Избранное - навигация (fav_page_, fav_delete_)
            'favorite_',  # Избранное - добавление сообщения в избранное
            'unfavorite_',  # Избранное - удаление сообщения из избранного
        ]
        
        # Проверяем callback-запросы для разрешенных действий
        if isinstance(event, CallbackQuery) and event.data:
            callback_data = event.data
            # Проверяем точное совпадение
            if callback_data in allowed_callbacks:
                print(f"INFO: Callback '{callback_data}' is allowed without access check. Access GRANTED.")
                logging.info(f"INFO: Callback '{callback_data}' is allowed without access check. Access GRANTED.")
                print("--- Access Check Finished ---\n")
                return await handler(event, data)
            # Проверяем префиксы
            for prefix in allowed_callback_prefixes:
                if callback_data.startswith(prefix):
                    print(f"INFO: Callback '{callback_data}' matches allowed prefix '{prefix}'. Access GRANTED.")
                    logging.info(f"INFO: Callback '{callback_data}' matches allowed prefix '{prefix}'. Access GRANTED.")
                    print("--- Access Check Finished ---\n")
                    return await handler(event, data)
        
        # Проверяем состояние FSM - если пользователь в определенных состояниях, пропускаем проверку доступа
        if isinstance(event, Message):
            state = data.get('state')
            if state:
                try:
                    current_state = await state.get_state()
                    # Если пользователь в состоянии поддержки или молитвы, пропускаем проверку доступа
                    if current_state == SupportState.waiting_for_message:
                        # Команды должны проходить обычный пайплайн
                        if event.text and event.text.strip().startswith('/'):
                            pass
                        else:
                            print(f"INFO: User is in support state. Access GRANTED for support message.")
                            logging.info(f"INFO: User is in support state. Access GRANTED for support message.")
                            print("--- Access Check Finished ---\n")
                            return await handler(event, data)
                    elif current_state == PrayerState.waiting_for_details:
                        # Пользователь уже выбрал тему молитвы, разрешаем отправку деталей
                        print(f"INFO: User is in prayer details state. Access GRANTED for prayer message.")
                        logging.info(f"INFO: User is in prayer details state. Access GRANTED for prayer message.")
                        print("--- Access Check Finished ---\n")
                        return await handler(event, data)
                except Exception as e:
                    logging.warning(f"WARNING: Could not get FSM state: {e}")
        
        # Проверяем, является ли это командой, которую нужно пропустить
        if isinstance(event, Message) and event.text:
            # Извлекаем команду из текста (учитываем формат /command или /command@botname)
            command_text = event.text.split()[0].split('@')[0] if event.text else ""
            print(f"DEBUG: Checking command '{command_text}' in allowed_commands: {command_text in allowed_commands}")
            logging.info(f"DEBUG: Checking command '{command_text}' in allowed_commands: {command_text in allowed_commands}")
            if command_text in allowed_commands:
                print(f"INFO: Command {command_text} is allowed without access check. Access GRANTED.")
                logging.info(f"INFO: Command {command_text} is allowed without access check. Access GRANTED.")
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
        
        # Шаг 4: Проверка пробного периода - НЕ активируем автоматически
        # Пробный период должен активироваться только через кнопку в /start или явный вызов activate_trial()
        user_data = get_user(user_id)
        trial_start = user_data.get('trial_start_date')
        
        if trial_start is None:
            # Пробный период еще не был активирован - отказываем в доступе
            # Пользователь должен активировать пробный период через /start
            print("INFO: Trial period has never been activated. Access DENIED.")
            print("RESULT: User must activate trial via /start button or subscribe.")
            print("--- Access Check Finished ---\n")
            no_access_text = (
                "✨ <b>Эта функция — часть Premium-доступа.</b>\n\n"
                "Для начала работы активируйте бесплатный пробный период на 3 дня через команду /start "
                "или оформите Premium-подписку: /subscribe"
            )
            if isinstance(event, Message):
                await event.answer(no_access_text, parse_mode='HTML')
            elif isinstance(event, CallbackQuery):
                await event.message.answer(no_access_text, parse_mode='HTML')
            return
        else:
            # Пробный период был активирован ранее, но истек - устанавливаем статус 'expired'
            if user_data.get('status') == 'free':
                user_data['status'] = 'expired'
                save_user_db()  # Сохраняем изменения
                logging.info(f"Пробный период истёк для user_id {user_id}, статус установлен на 'expired'")
            
            print("RESULT: Trial period was activated previously but has expired. Access DENIED.")
            print("--- Access Check Finished ---\n")
            no_access_text = (
                "✨ <b>Эта функция — часть Premium-доступа.</b>\n\n"
                "Ваш пробный период истек. Для продолжения использования Premium-функций оформите подписку: /subscribe"
            )
            if isinstance(event, Message):
                await event.answer(no_access_text, parse_mode='HTML')
            elif isinstance(event, CallbackQuery):
                await event.message.answer(no_access_text, parse_mode='HTML')
            return

# Главный декоратор (middleware)
check_access = AccessCheckerMiddleware()