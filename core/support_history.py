import json
import logging
import os
from datetime import datetime

SUPPORT_HISTORY_FILE = "support_history.json"

support_history = {}

def load_support_history() -> None:
    global support_history
    if os.path.exists(SUPPORT_HISTORY_FILE):
        try:
            with open(SUPPORT_HISTORY_FILE, 'r', encoding='utf-8') as f:
                support_history = json.load(f)
        except Exception as e:
            logging.error(f"Ошибка при загрузке истории поддержки: {e}", exc_info=True)
            support_history = {}
    else:
        support_history = {}

def save_support_history() -> None:
    try:
        with open(SUPPORT_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(support_history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Ошибка при сохранении истории поддержки: {e}", exc_info=True)

def add_support_entry(
    user_id: int,
    direction: str,
    text: str | None,
    content_type: str,
    username: str | None,
    first_name: str | None,
    message_id: int | None = None
) -> None:
    entry = {
        "timestamp": datetime.now().isoformat(),
        "direction": direction,
        "text": text,
        "content_type": content_type,
        "username": username,
        "first_name": first_name,
        "message_id": message_id
    }
    key = str(user_id)
    support_history.setdefault(key, []).append(entry)
    save_support_history()

load_support_history()
