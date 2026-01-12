# База данных пользователей с сохранением в файл
import json
import os
from datetime import datetime # Импортируем datetime

USER_DB_FILE = "user_db.json"

# Загружаем данные из файла при старте
user_db = {}

def load_user_db():
    """
    Загружает базу данных пользователей из файла.
    Конвертирует строковые даты обратно в datetime объекты.
    """
    global user_db
    if os.path.exists(USER_DB_FILE):
        try:
            with open(USER_DB_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Конвертируем ключи обратно в int (JSON сохраняет ключи как строки)
                user_db = {}
                for k, v in data.items():
                    user_id = int(k)
                    user_data = {}
                    for key, value in v.items():
                        # Конвертируем строковые даты обратно в datetime
                        if key in ('trial_start_date', 'subscription_end_date') and isinstance(value, str):
                            try:
                                user_data[key] = datetime.fromisoformat(value)
                            except (ValueError, TypeError):
                                # Если не удалось распарсить, оставляем как строку
                                user_data[key] = value
                        else:
                            user_data[key] = value
                    user_db[user_id] = user_data
                logging.info(f"База данных пользователей загружена: {len(user_db)} пользователей")
        except Exception as e:
            logging.error(f"Ошибка при загрузке базы данных пользователей: {e}", exc_info=True)
            user_db = {}
    else:
        logging.info("Файл базы данных пользователей не найден, создается новая база")
        user_db = {}

def save_user_db():
    """
    Сохраняет базу данных пользователей в файл.
    """
    try:
        # Конвертируем datetime объекты в строки для JSON
        data_to_save = {}
        for user_id, user_data in user_db.items():
            data_to_save[str(user_id)] = {}
            for key, value in user_data.items():
                if isinstance(value, datetime):
                    data_to_save[str(user_id)][key] = value.isoformat()
                else:
                    data_to_save[str(user_id)][key] = value
        
        with open(USER_DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Ошибка при сохранении базы данных пользователей: {e}")

# Импортируем logging для использования в функциях
import logging

# Загружаем данные при импорте модуля
load_user_db()

def get_user(user_id):
    """
    Возвращает данные пользователя или создает новую запись.
    Автоматически сохраняет изменения в файл.
    """
    if user_id not in user_db:
        user_db[user_id] = {
            'notifications': {'morning': True, 'daily': True, 'evening': True},
            'prayer_mode_topic': None,
            'nameday_persons': [], # Добавляем список для хранения имен близких
            'favorites': [] # Добавляем список для хранения избранных сообщений
        }
        save_user_db()  # Сохраняем при создании нового пользователя
    return user_db[user_id]

def set_prayer_topic(user_id, topic):
    """
    Устанавливает тему для режима молитвы.
    """
    user = get_user(user_id)
    user['prayer_mode_topic'] = topic
    save_user_db()

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
        save_user_db()

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
        save_user_db()

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
    save_user_db()
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
    removed = len(user['favorites']) < initial_len
    if removed:
        save_user_db()
    return removed

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
