"""
Тестовый скрипт для проверки обработчика команды /admin
"""
import os
import sys
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

print("=" * 60)
print("ТЕСТ ОБРАБОТЧИКА КОМАНДЫ /admin")
print("=" * 60)

# Проверка 1: Переменные окружения
print("\n1. Проверка переменных окружения:")
ADMIN_ID = os.getenv('ADMIN_ID')
BOT_TOKEN = os.getenv('BOT_TOKEN')
print(f"   ADMIN_ID: {ADMIN_ID}")
print(f"   BOT_TOKEN: {'Установлен' if BOT_TOKEN else 'НЕ УСТАНОВЛЕН'}")

if not ADMIN_ID:
    print("   ❌ ОШИБКА: ADMIN_ID не установлен!")
    sys.exit(1)

# Проверка 2: Импорт модулей
print("\n2. Проверка импорта модулей:")
try:
    from handlers.admin_handler import router, get_admin_id
    print("   ✅ admin_handler импортирован успешно")
except Exception as e:
    print(f"   ❌ Ошибка импорта admin_handler: {e}")
    sys.exit(1)

try:
    from core.user_database import user_db
    print("   ✅ user_database импортирован успешно")
except Exception as e:
    print(f"   ❌ Ошибка импорта user_database: {e}")
    sys.exit(1)

# Проверка 3: Роутер и обработчики
print("\n3. Проверка роутера:")
print(f"   Роутер создан: {router is not None}")
print(f"   Количество обработчиков: {len(router.sub_routers) if hasattr(router, 'sub_routers') else 'N/A'}")

# Проверка 4: Функция get_admin_id
print("\n4. Проверка функции get_admin_id:")
admin_id_from_func = get_admin_id()
print(f"   ADMIN_ID из функции: {admin_id_from_func}")
if admin_id_from_func == ADMIN_ID:
    print("   ✅ Функция работает корректно")
else:
    print("   ❌ ОШИБКА: Функция возвращает неверное значение!")

# Проверка 5: Проверка user_db
print("\n5. Проверка базы данных пользователей:")
print(f"   Количество пользователей в базе: {len(user_db)}")
if len(user_db) > 0:
    print(f"   Примеры ID пользователей: {list(user_db.keys())[:5]}")

# Проверка 6: Проверка фильтров
print("\n6. Проверка фильтров обработчика:")
# Попробуем найти обработчик команды /admin
try:
    from aiogram.filters import Command
    from aiogram import F
    
    # Проверяем, что фильтры доступны
    print("   ✅ Фильтры Command и F доступны")
    
    # Проверяем синтаксис комбинированного фильтра
    test_filter = Command("admin") | (F.text == "/admin")
    print("   ✅ Комбинированный фильтр создан успешно")
except Exception as e:
    print(f"   ❌ Ошибка при проверке фильтров: {e}")

print("\n" + "=" * 60)
print("ТЕСТ ЗАВЕРШЕН")
print("=" * 60)
print("\nЕсли все проверки пройдены, обработчик должен работать.")
print("Проверьте файл bot.log после запуска бота и выполнения команды /admin")

