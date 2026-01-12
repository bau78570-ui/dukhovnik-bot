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
                
                # Миграция данных: добавляем отсутствующие поля для существующих пользователей
                _migrate_user_data()
                
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
    Использует atomic write (запись во временный файл, затем переименование)
    для предотвращения потери данных при конкурентных вызовах.
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
        
        # Atomic write: пишем во временный файл, затем переименовываем
        temp_file = USER_DB_FILE + '.tmp'
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=2)
        
        # Атомарное переименование (на Windows может потребоваться удаление старого файла)
        if os.path.exists(USER_DB_FILE):
            os.replace(temp_file, USER_DB_FILE)
        else:
            os.rename(temp_file, USER_DB_FILE)
    except Exception as e:
        logging.error(f"Ошибка при сохранении базы данных пользователей: {e}", exc_info=True)
        # Удаляем временный файл в случае ошибки
        if os.path.exists(USER_DB_FILE + '.tmp'):
            try:
                os.remove(USER_DB_FILE + '.tmp')
            except:
                pass

# Импортируем logging для использования в функциях
import logging

def _migrate_user_data():
    """
    Миграция данных: добавляет отсутствующие поля для существующих пользователей.
    Вызывается после загрузки данных из файла.
    """
    default_fields = {
        'notifications': {'morning': True, 'daily': True, 'evening': True},
        'prayer_mode_topic': None,
        'nameday_persons': [],
        'favorites': []
    }
    
    migrated_count = 0
    for user_id, user_data in user_db.items():
        needs_save = False
        for field, default_value in default_fields.items():
            if field not in user_data:
                user_data[field] = default_value
                needs_save = True
        
        if needs_save:
            migrated_count += 1
    
    if migrated_count > 0:
        logging.info(f"Миграция данных: обновлено {migrated_count} пользователей")
        # Сохраняем мигрированные данные
        try:
            save_user_db()
        except Exception as e:
            logging.warning(f"Не удалось сохранить мигрированные данные: {e}")

# Загружаем данные при импорте модуля
load_user_db()

def get_user(user_id):
    """
    Возвращает данные пользователя или создает новую запись.
    Автоматически инициализирует отсутствующие поля для существующих пользователей.
    Автоматически сохраняет изменения в файл при создании нового пользователя.
    """
    if user_id not in user_db:
        user_db[user_id] = {
            'notifications': {'morning': True, 'daily': True, 'evening': True},
            'prayer_mode_topic': None,
            'nameday_persons': [], # Добавляем список для хранения имен близких
            'favorites': [] # Добавляем список для хранения избранных сообщений
        }
        save_user_db()  # Сохраняем при создании нового пользователя
    else:
        # Инициализируем отсутствующие поля для существующих пользователей (на случай, если миграция не сработала)
        user_data = user_db[user_id]
        if 'notifications' not in user_data:
            user_data['notifications'] = {'morning': True, 'daily': True, 'evening': True}
        if 'prayer_mode_topic' not in user_data:
            user_data['prayer_mode_topic'] = None
        if 'nameday_persons' not in user_data:
            user_data['nameday_persons'] = []
        if 'favorites' not in user_data:
            user_data['favorites'] = []
    
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
    # Безопасная инициализация поля, если его нет
    if 'nameday_persons' not in user:
        user['nameday_persons'] = []
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
    # Безопасная инициализация поля, если его нет
    if 'nameday_persons' not in user:
        user['nameday_persons'] = []
        return
    
    if name in user['nameday_persons']:
        user['nameday_persons'].remove(name)
        save_user_db()

def add_favorite_message(user_id: int, bot_message_id: int, original_message_id: int, content: str, image_name: str = None):
    """
    Добавляет сообщение в избранное пользователя.
    """
    user = get_user(user_id)
    # Безопасная инициализация поля, если его нет
    if 'favorites' not in user:
        user['favorites'] = []
    
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
    # Безопасная инициализация поля, если его нет
    if 'favorites' not in user:
        user['favorites'] = []
        return False
    
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
