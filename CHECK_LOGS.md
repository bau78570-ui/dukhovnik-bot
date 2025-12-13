# Как проверить логи бота

## Где находятся логи

После запуска бота все логи сохраняются в файле **`bot.log`** в корневой папке проекта.

## Как проверить логи

### Вариант 1: Через командную строку (PowerShell)

```powershell
# Просмотр последних 50 строк логов
Get-Content bot.log -Tail 50

# Поиск записей о команде /admin
Select-String -Path bot.log -Pattern "ADMIN|admin" | Select-Object -Last 20

# Просмотр всех записей о команде /admin
Select-String -Path bot.log -Pattern "ADMIN COMMAND"
```

### Вариант 2: Через текстовый редактор

1. Откройте файл `bot.log` в любом текстовом редакторе (Notepad, VS Code и т.д.)
2. Найдите строки, содержащие "ADMIN COMMAND" или "admin"
3. Скопируйте эти строки для анализа

### Вариант 3: В реальном времени (если бот запущен)

```powershell
# Просмотр логов в реальном времени
Get-Content bot.log -Wait -Tail 20
```

## Что искать в логах

После выполнения команды `/admin` в боте, в логах должны появиться записи:

1. **Если обработчик сработал:**
   ```
   === ADMIN COMMAND ATTEMPT ===
   User ID: 243234870
   ADMIN_ID from env: 243234870
   Message text: /admin
   Admin access granted for user_id: 243234870
   Admin stats sent: total_users=X, active_subscriptions=Y
   ```

2. **Если команда перехватывается text_handler:**
   ```
   Text handler: skipping command /admin
   ```

3. **Если есть ошибка доступа:**
   ```
   Access denied: user_id X != admin_id 243234870
   ```

## Если команда не работает

1. Убедитесь, что бот перезапущен после изменений
2. Проверьте файл `bot.log` на наличие записей о команде `/admin`
3. Если записей нет вообще - обработчик не вызывается (проблема с регистрацией)
4. Если есть "Text handler: skipping" - команда перехватывается text_handler
5. Если есть "Access denied" - проверьте ваш Telegram ID

## Быстрая проверка

Запустите этот скрипт для проверки:
```powershell
python test_admin_handler.py
```

