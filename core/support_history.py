import json
import logging
import os
import threading
from datetime import datetime

SUPPORT_HISTORY_FILE = "support_history.json"

support_history: dict[str, list[dict]] = {}
support_status: dict[str, str] = {}
_support_lock = threading.Lock()

def load_support_history() -> None:
    global support_history, support_status
    with _support_lock:
        if os.path.exists(SUPPORT_HISTORY_FILE):
            try:
                with open(SUPPORT_HISTORY_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict) and "history" in data:
                        support_history = data.get("history", {})
                        support_status = data.get("status", {})
                    else:
                        support_history = data if isinstance(data, dict) else {}
                        support_status = {}
            except Exception as e:
                logging.error(f"Ошибка при загрузке истории поддержки: {e}", exc_info=True)
                support_history = {}
                support_status = {}
        else:
            support_history = {}
            support_status = {}

def save_support_history() -> None:
    with _support_lock:
        try:
            with open(SUPPORT_HISTORY_FILE, 'w', encoding='utf-8') as f:
                payload = {"history": support_history, "status": support_status}
                json.dump(payload, f, ensure_ascii=False, indent=2)
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
    with _support_lock:
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

def get_support_history(user_id: int) -> list[dict]:
    with _support_lock:
        return list(support_history.get(str(user_id), []))

def get_support_status(user_id: int) -> str:
    with _support_lock:
        return support_status.get(str(user_id), "новый")

def set_support_status(user_id: int, status: str) -> None:
    with _support_lock:
        support_status[str(user_id)] = status
        save_support_history()

load_support_history()
