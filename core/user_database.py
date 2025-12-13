# Временная база данных пользователей
user_db = {}

from datetime import datetime # Импортируем datetime

def get_user(user_id):
    """
    Возвращает данные пользователя или создает новую запись.
    """
    if user_id not in user_db:
        user_db[user_id] = {
            'notifications': {'morning': True, 'daily': True, 'evening': True},
            'prayer_mode_topic': None,
            'nameday_persons': [], # Добавляем список для хранения имен близких
            'favorites': [] # Добавляем список для хранения избранных сообщений
        }
    return user_db[user_id]

def set_prayer_topic(user_id, topic):
    """
    Устанавливает тему для режима молитвы.
    """
    user = get_user(user_id)
    user['prayer_mode_topic'] = topic

def get_prayer_topic(user_id):
    """
    Получает текущую тему молитвы пользователя.
    """
    user = get_user(user_id)
    return user.get('prayer_mode_topic')

def add_nameday_person(user_id: int, name: str):
    """
    Добавляет имя близкого человека в список для напоминаний об именинах.
    """
    user = get_user(user_id)
    if name not in user['nameday_persons']:
        user['nameday_persons'].append(name)

def get_nameday_persons(user_id: int) -> list[str]:
    """
    Возвращает список имен близких человека для напоминаний об именинах.
    """
    user = get_user(user_id)
    return user.get('nameday_persons', [])

def remove_nameday_person(user_id: int, name: str):
    """
    Удаляет имя близкого человека из списка для напоминаний об именинах.
    """
    user = get_user(user_id)
    if name in user['nameday_persons']:
        user['nameday_persons'].remove(name)

def add_favorite_message(user_id: int, bot_message_id: int, original_message_id: int, content: str, image_name: str = None):
    """
    Добавляет сообщение в избранное пользователя.
    """
    user = get_user(user_id)
    favorite_entry = {
        'bot_message_id': bot_message_id,
        'original_message_id': original_message_id,
        'content': content,
        'image_name': image_name,
        'timestamp': datetime.now().isoformat()
    }
    user['favorites'].append(favorite_entry)
    return True

def get_favorite_messages(user_id: int) -> list[dict]:
    """
    Возвращает список избранных сообщений пользователя.
    """
    user = get_user(user_id)
    return user.get('favorites', [])

def remove_favorite_message(user_id: int, bot_message_id: int) -> bool:
    """
    Удаляет сообщение из избранного пользователя по bot_message_id.
    """
    user = get_user(user_id)
    initial_len = len(user['favorites'])
    user['favorites'] = [fav for fav in user['favorites'] if fav['bot_message_id'] != bot_message_id]
    return len(user['favorites']) < initial_len

def get_all_users_with_namedays() -> dict[int, list[str]]:
    """
    Возвращает словарь всех пользователей, у которых есть настроенные именины,
    в формате {user_id: [name1, name2, ...]}
    """
    users_with_namedays = {}
    for user_id, user_data in user_db.items():
        if user_data.get('nameday_persons'):
            users_with_namedays[user_id] = user_data['nameday_persons']
    return users_with_namedays

async def get_bot_stats() -> dict:
    """
    Возвращает статистику бота:
    - Количество всех пользователей в БД
    - Количество пользователей с активной подпиской (Premium)
    """
    from core.subscription_checker import is_premium
    
    total_users = len(user_db)
    active_subscriptions = 0
    
    # Подсчитываем пользователей с активной подпиской
    for user_id in user_db.keys():
        if await is_premium(user_id):
            active_subscriptions += 1
    
    return {
        'total_users': total_users,
        'active_subscriptions': active_subscriptions
    }