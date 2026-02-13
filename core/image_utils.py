"""
Утилиты для выбора локальных изображений из базы бота.
Все изображения берутся только из assets/images/ — никогда с внешних сайтов.
"""
import os
import random


def pick_local_image(prefer: str | None = None, exclude_daily_word: bool = False) -> str | None:
    """
    Выбирает локальное изображение из базы бота (только наши файлы, не с внешних сайтов).

    :param prefer: Предпочтительный файл (например 'daily_quote.png') или папка (например 'daily_word').
                   Если указана папка — выбирается случайный файл из неё.
    :param exclude_daily_word: Если True — не использовать папку daily_word (для календаря, чтобы избежать
                              изображений, которые могли быть загружены с сайтов).
    :return: Относительный путь вида 'daily_word/xxx.png' или 'logo.png', или None если ничего не найдено.
    """
    assets_images = os.path.join('assets', 'images')
    if not os.path.exists(assets_images):
        return None

    # Предпочтение: конкретный файл
    if prefer and not prefer.endswith('/'):
        candidate = os.path.join(assets_images, prefer)
        if os.path.isfile(candidate):
            return prefer

    # Предпочтение: папка (например daily_word), если не исключена
    if prefer and not exclude_daily_word:
        folder = os.path.join(assets_images, prefer.rstrip('/'))
        if os.path.isdir(folder):
            files = [f for f in os.listdir(folder) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
            if files:
                return f"{prefer.rstrip('/')}/{random.choice(files)}"

    # Пробуем daily_word (только если не исключена)
    if not exclude_daily_word:
        daily_word = os.path.join(assets_images, 'daily_word')
        if os.path.isdir(daily_word):
            files = [f for f in os.listdir(daily_word) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
            if files:
                return f"daily_word/{random.choice(files)}"

    # Пробуем daily_quote.png
    if os.path.isfile(os.path.join(assets_images, 'daily_quote.png')):
        return 'daily_quote.png'

    # Запасной вариант: logo.png
    if os.path.isfile(os.path.join(assets_images, 'logo.png')):
        return 'logo.png'

    return None


def is_external_url(value: str | None) -> bool:
    """Проверяет, является ли значение внешним URL (http/https)."""
    if not value or not isinstance(value, str):
        return False
    return value.strip().startswith(('http://', 'https://'))
