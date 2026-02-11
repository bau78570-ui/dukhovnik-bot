#!/bin/bash
# Скрипт для корректного перезапуска бота через systemd

echo "=== Остановка всех процессов Python бота ==="
killall -9 python python3 2>/dev/null || echo "Нет запущенных процессов Python"

echo "=== Очистка Python cache ==="
find /opt/dukhovnik_bot -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null
find /opt/dukhovnik_bot -name '*.pyc' -delete 2>/dev/null

echo "=== Перезапуск systemd сервиса ==="
sudo systemctl restart dukhovnik-bot.service

echo "=== Ожидание 5 секунд ==="
sleep 5

echo "=== Проверка статуса ==="
sudo systemctl status dukhovnik-bot.service --no-pager -l

echo "=== Последние 20 строк лога ==="
tail -20 /opt/dukhovnik_bot/bot.log

echo "=== Готово! ==="
