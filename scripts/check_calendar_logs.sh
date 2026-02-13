#!/bin/bash
# Скрипт для проверки логов календаря на сервере
# Запуск: ./scripts/check_calendar_logs.sh
# Или: bash scripts/check_calendar_logs.sh

LOG_FILE="${1:-/opt/dukhovnik_bot/bot.log}"

echo "=== Проверка логов календаря (файл: $LOG_FILE) ==="
echo ""

echo "--- Calendar handler: какой image_name передаётся ---"
grep -E "Calendar /calendar:|image_name=" "$LOG_FILE" 2>/dev/null | tail -30

echo ""
echo "--- Блокировка pravoslavie (если есть — наша защита сработала) ---"
grep "Пропуск изображения с pravoslavie" "$LOG_FILE" 2>/dev/null | tail -10

echo ""
echo "--- Последние ошибки ---"
grep -iE "error|ошибка|Exception" "$LOG_FILE" 2>/dev/null | tail -10

echo ""
echo "--- Последние 15 строк лога ---"
tail -15 "$LOG_FILE" 2>/dev/null
