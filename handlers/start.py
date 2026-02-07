from aiogram import F, Router, Bot
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, FSInputFile, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext # Импортируем FSMContext
from datetime import datetime # Импортируем datetime
from core.content_sender import send_and_delete_previous, send_content_message # Импортируем новую централизованную функцию
from core.user_database import get_user, user_db, save_user_db # Импортируем get_user, user_db и save_user_db
from core.subscription_checker import is_premium # Импортируем is_premium
from core.yandex_metrika import track_bot_start, track_new_user, track_feature_used # Импортируем Яндекс.Метрику
import logging # Импортируем logging
import asyncio # Импортируем asyncio для задержек
import os # Импортируем os для ADMIN_ID
from dotenv import load_dotenv
import re # Для парсинга UTM параметров с regex

load_dotenv()
ADMIN_ID = os.getenv("ADMIN_ID", "")

# Создаем роутер для этого обработчика
router = Router()


def parse_start_params(text: str) -> dict:
    """
    Парсит параметры из команды /start.
    Поддерживает форматы:
    - /start utm_source=telegram--utm_campaign=christmas--ref=12345
    - /start@botname utm_source=telegram--utm_campaign=christmas
    - /start source-telegram-campaign-christmas-ref-12345
    Возвращает словарь с параметрами.
    """
    params = {}
    
    if not text or not text.strip().startswith('/start'):
        return params
    
    # Убираем "/start" и опционально "@botname" используя regex
    # Паттерн: /start, затем опционально @имя_бота (буквы, цифры, подчеркивания), затем пробел и параметры
    match = re.match(r'^/start(?:@[\w-]+)?\s*(.*)', text.strip())
    
    if not match:
        return params
    
    param_string = match.group(1).strip()
    
    if not param_string:
        return params
    
    # Метод 1: Парсим формат key=value с разделителем "--"
    # Формат: utm_source=telegram--utm_campaign=christmas--ref=12345
    if '--' in param_string:
        parts = param_string.split('--')
        for part in parts:
            if '=' in part:
                key, value = part.split('=', 1)
                params[key.strip()] = value.strip()
    
    # Метод 2: Парсим формат через одинарный дефис (короткий формат)
    # Формат: source-telegram-campaign-christmas-ref-12345
    elif '-' in param_string:
        parts = param_string.split('-')
        # Обрабатываем пары ключ-значение
        i = 0
        while i < len(parts) - 1:
            key = parts[i].strip()
            value = parts[i + 1].strip()
            
            # Преобразуем короткие ключи в полные UTM ключи
            if key in ['source', 'medium', 'campaign', 'term', 'content']:
                key = f'utm_{key}'
            
            params[key] = value
            i += 2
    
    # Метод 3: Используем regex для поиска всех паттернов key=value
    # Формат: utm_source=telegram_utm_campaign=christmas (с подчеркиваниями)
    else:
        # Ищем все паттерны вида "ключ=значение", где ключ может содержать подчеркивания
        # Паттерн: буквы/цифры/подчеркивания, затем =, затем значение до следующего ключа или конца
        pattern = r'([a-zA-Z_][a-zA-Z0-9_]*)=([^=]+?)(?=\s+[a-zA-Z_][a-zA-Z0-9_]*=|$)'
        matches = re.findall(pattern, param_string)
        
        for key, value in matches:
            params[key.strip()] = value.strip()
    
    return params

@router.message(CommandStart())
async def command_start_handler(message: Message, bot: Bot, state: FSMContext) -> None:
    """
    Этот обработчик будет срабатывать на команду /start.
    Для новых пользователей показывает 3-сообщение welcome-онбординг.
    Поддерживает UTM-трекинг и реферальные ссылки.
    """
    # Регистрируем пользователя в базе данных
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Получаем или создаем запись пользователя
    user_data = get_user(user_id)
    
    # Проверяем, прошел ли пользователь онбординг
    is_new_user = not user_data.get('onboarded', False)
    
    # Получаем имя пользователя для персонализации
    user_name = message.from_user.first_name or "друг"
    username = message.from_user.username or ""
    
    # Парсим UTM параметры и реферальные ссылки
    start_params = parse_start_params(message.text)
    
    # Сохраняем UTM параметры для новых пользователей
    if is_new_user:
        # Если параметров нет - устанавливаем utm_source='organic'
        if start_params:
            utm_source = start_params.get('utm_source', 'direct')
            utm_medium = start_params.get('utm_medium', '')
            utm_campaign = start_params.get('utm_campaign', '')
            utm_term = start_params.get('utm_term', '')
            utm_content = start_params.get('utm_content', '')
            referrer_id = start_params.get('ref', '')
        else:
            # Новый пользователь без параметров = органический трафик
            utm_source = 'organic'
            utm_medium = ''
            utm_campaign = ''
            utm_term = ''
            utm_content = ''
            referrer_id = ''
        
        # Сохраняем UTM данные
        user_data['utm_source'] = utm_source
        user_data['utm_medium'] = utm_medium
        user_data['utm_campaign'] = utm_campaign
        user_data['utm_term'] = utm_term
        user_data['utm_content'] = utm_content
        user_data['first_visit_date'] = datetime.now()
        
        # Сохраняем username для контакта
        if username:
            user_data['username'] = username
        
        # Обрабатываем реферальную ссылку
        if referrer_id:
            user_data['referrer_id'] = referrer_id
            # Увеличиваем счетчик рефералов у реферера (thread-safe)
            try:
                referrer_id_int = int(referrer_id)
                from core.user_database import increment_referral_count
                increment_referral_count(referrer_id_int, user_id)
            except (ValueError, TypeError):
                logging.error(f"Некорректный referrer_id: {referrer_id}")
        
        save_user_db()
        
        # Логирование с UTM данными
        utm_log = f"utm_source={utm_source}"
        if utm_campaign:
            utm_log += f", utm_campaign={utm_campaign}"
        if utm_medium:
            utm_log += f", utm_medium={utm_medium}"
        if referrer_id:
            utm_log += f", ref={referrer_id}"
        
        logging.info(f"Новый пользователь {user_id} (@{username or 'no_username'}) из источника: {utm_log}")
    elif not is_new_user and not user_data.get('utm_source'):
        # Для старых пользователей без UTM данных ставим "organic"
        user_data['utm_source'] = 'organic'
        if username and not user_data.get('username'):
            user_data['username'] = username
        save_user_db()
    
    # Трекинг события запуска бота в Яндекс.Метрике
    asyncio.create_task(track_bot_start(user_id, is_new_user=is_new_user))
    
    # Если новый пользователь - трекаем регистрацию
    if is_new_user:
        # utm_source уже сохранен в user_data на строках выше
        asyncio.create_task(track_new_user(user_id, utm_source=user_data.get('utm_source', 'organic')))
    
    # Сначала убираем старую клавиатуру (сброс кэша Telegram)
    await message.answer("♻️", reply_markup=ReplyKeyboardRemove())
    
    # === WELCOME-ОНБОРДИНГ ДЛЯ НОВЫХ ПОЛЬЗОВАТЕЛЕЙ ===
    if is_new_user:
        logging.info(f"Запуск welcome-онбординга для пользователя {user_id} ({user_name})")
        
        try:
            # Сообщение 1: Приветствие с изображением
            await bot.send_chat_action(chat_id, "typing")
            welcome_text = (
                f"🕊️ <b>Мир вам, {user_name}!</b>\n\n"
                "Я — <b>Духовник</b>, ваш личный помощник в вопросах православной веры и духовного роста. 🙏\n\n"
                "Я здесь, чтобы поддержать вас в духовном поиске, ответить на вопросы и помочь обрести внутренний покой.\n\n"
                "✨ <i>Более 5000 православных христиан уже доверяют мне свои мысли и вопросы.</i>"
            )
            await send_content_message(
                bot=bot,
                chat_id=chat_id,
                text=welcome_text,
                image_name='onboarding.png'
            )
            
            # Задержка для естественности
            await asyncio.sleep(2)
        except asyncio.CancelledError:
            logging.warning(f"Онбординг прерван для пользователя {user_id} (задача отменена)")
            raise
        except Exception as e:
            logging.error(f"Ошибка при отправке приветственного сообщения пользователю {user_id}: {e}")
        
        try:
            # Сообщение 2: Гайд по возможностям
            await bot.send_chat_action(chat_id, "typing")
            await asyncio.sleep(1.5)
            
            guide_text = (
                "📚 <b>Что я умею:</b>\n\n"
                "💬 <b>Безлимитные беседы с ИИ</b>\n"
                "Задавайте любые вопросы о вере, Писании, церковной жизни — отвечу понятно и с опорой на православную традицию\n\n"
                "📖 <b>Ежедневное «Слово Дня»</b>\n"
                "Каждый день в 14:00 — глубокие размышления и вдохновение из Священного Писания\n\n"
                "🗓️ <b>Православный календарь</b>\n"
                "Праздники, посты, именины — всё в одном месте с подробными объяснениями\n\n"
                "🙏 <b>Персональные молитвы</b>\n"
                "Составлю молитву специально для вашей ситуации — о здоровье, семье, работе или душевном покое\n\n"
                "⚙️ <b>Умные уведомления</b>\n"
                "Утреннее вдохновение (8:00), дневное слово (14:00) и вечерние размышления (20:00)\n\n"
                "🎁 <b>Всё это БЕСПЛАТНО первый месяц!</b>\n"
                "Полный доступ без ограничений — попробуйте и убедитесь сами."
            )
            await message.answer(guide_text, parse_mode='HTML')
            
            # Задержка перед призывом к действию
            await asyncio.sleep(2)
        except asyncio.CancelledError:
            logging.warning(f"Онбординг прерван для пользователя {user_id} (задача отменена на этапе 2)")
            raise
        except Exception as e:
            logging.error(f"Ошибка при отправке гайда пользователю {user_id}: {e}")
        
        try:
            # Сообщение 3: Призыв к действию с кнопками
            await bot.send_chat_action(chat_id, "typing")
            await asyncio.sleep(1)
            
            # Создаем клавиатуру с быстрыми действиями
            action_builder = InlineKeyboardBuilder()
            action_builder.button(text="🎁 Активировать 1 месяц бесплатно", callback_data="activate_free_period")
            action_builder.button(text="💬 Задать вопрос Духовнику", callback_data="start_chat")
            action_builder.button(text="🗓️ Посмотреть календарь", callback_data="show_calendar")
            action_builder.adjust(1)
            
            call_to_action = (
                "🚀 <b>Начните прямо сейчас!</b>\n\n"
                "🔹 Нажмите кнопку ниже, чтобы <b>активировать 1 месяц бесплатного доступа</b>\n"
                "🔹 Или просто напишите мне свой вопрос — я уже готов помочь!\n\n"
                "💡 <b>Быстрый старт:</b>\n"
                "• Команда /dukhovnik — начать беседу\n"
                "• Команда /prayer — создать молитву\n"
                "• Команда /calendar — православный календарь\n"
                "• Команда /subscribe — активировать доступ\n\n"
                "📢 <b>Поделитесь ботом с друзьями!</b>\n"
                "Помогите близким найти духовную поддержку — пусть они тоже получат 1 месяц бесплатного доступа.\n\n"
                "🙏 <i>Да хранит вас Господь на всех путях ваших!</i>"
            )
            
            await message.answer(
                call_to_action,
                reply_markup=action_builder.as_markup(),
                parse_mode='HTML'
            )
        except asyncio.CancelledError:
            logging.warning(f"Онбординг прерван для пользователя {user_id} (задача отменена на этапе 3)")
            raise
        except Exception as e:
            logging.error(f"Ошибка при отправке призыва к действию пользователю {user_id}: {e}")
        
        # Отмечаем, что пользователь прошел онбординг
        user_data['onboarded'] = True
        user_data['onboarded_date'] = datetime.now()
        save_user_db()
        
        logging.info(f"Welcome-онбординг завершен для пользователя {user_id}")
        return
    
    # === СТАНДАРТНЫЙ /START ДЛЯ ВЕРНУВШИХСЯ ПОЛЬЗОВАТЕЛЕЙ ===
    # Проверяем статус пользователя
    from core.subscription_checker import is_trial_active, is_subscription_active, is_free_period_active
    
    trial_was_activated = user_data.get('trial_start_date') is not None
    trial_is_active = await is_trial_active(user_id)
    has_subscription = await is_subscription_active(user_id)
    has_free_period = await is_free_period_active(user_id)
    
    # Отправка изображения с приветственной подписью
    welcome_caption = (
        f"🕊️ <b>С возвращением, {user_name}!</b>\n\n"
        "Я — <b>Духовник</b>, ваш цифровой собеседник в вопросах веры. "
        "Я здесь, чтобы помочь и поддержать вас в духовном поиске."
    )
    await send_content_message(
        bot=bot,
        chat_id=chat_id,
        text=welcome_caption,
        image_name='onboarding.png'
    )

    # Отправка дисклеймера и кнопок
    builder = InlineKeyboardBuilder()
    
    # Показываем кнопку активации бесплатного периода, если он еще не активирован
    free_period_start = user_data.get('free_period_start')
    if free_period_start is None:
        builder.button(text="🎁 Активировать 1 месяц бесплатно", callback_data="activate_free_period")
    # Или кнопку пробного периода, если он еще не был активирован
    elif not trial_was_activated:
        builder.button(text="✅ Начать 3 дня бесплатно", callback_data="start_trial")
    
    builder.button(text="📄 Условия использования", url="https://teletype.in/@doc_content/IWP-06AxhyO")
    builder.adjust(1)

    disclaimer_text = (
        "<i>Важно: Я — нейросеть, а не священник. Мои ответы основаны на православных учениях и текстах, "
        "но не являются каноническими указаниями и не заменяют Таинств Церкви и живого общения с духовником. "
        "Проект является частной инициативой и не связан с РПЦ.</i>"
    )
    
    # Формируем текст в зависимости от статуса пользователя
    if has_subscription:
        status_text = "🎉 У вас активна Premium-подписка! Вы можете пользоваться всеми функциями бота."
    elif has_free_period:
        status_text = "✨ У вас активен бесплатный период на 1 месяц! Наслаждайтесь всеми функциями бота."
    elif trial_is_active:
        status_text = "✅ У вас активен бесплатный пробный период. Вы можете пользоваться всеми функциями бота."
    elif trial_was_activated:
        status_text = "💳 Ваш пробный период истек. Для продолжения использования Premium-функций оформите подписку: /subscribe"
    else:
        status_text = "Вы можете начать наш разговор прямо сейчас. Активируйте бесплатный период для полного доступа ко всем функциям."

    info_text = f"{disclaimer_text}\n\n{status_text}"

    await message.answer(
        text=info_text,
        reply_markup=builder.as_markup(),
        parse_mode='HTML'
    )



@router.callback_query(F.data == "start_trial")
async def start_trial_handler(query: CallbackQuery, bot: Bot, state: FSMContext):
    """
    Этот обработчик будет срабатывать на нажатие инлайн-кнопки
    с callback_data="start_trial" и активировать пробный период.
    """
    user_id = query.from_user.id
    from core.subscription_checker import activate_trial, TRIAL_DURATION_DAYS # Импортируем здесь, чтобы избежать циклического импорта

    if await activate_trial(user_id):
        await query.message.edit_text(
            text=f"🎉 <b>Поздравляем!</b> Ваш бесплатный пробный период на {TRIAL_DURATION_DAYS} дня активирован.\n"
                 "Теперь вы можете пользоваться всеми функциями бота без ограничений!",
            parse_mode='HTML'
        )
    else:
        await query.message.edit_text(
            text="Вы уже активировали пробный период ранее или он истек. "
                 "Для продолжения использования Premium-функций, пожалуйста, оформите подписку: /subscribe",
            parse_mode='HTML'
        )
    await query.answer()


@router.callback_query(F.data == "start_chat")
async def start_chat_handler(query: CallbackQuery, bot: Bot):
    """
    Обработчик кнопки "Задать вопрос Духовнику" из онбординга.
    """
    await query.answer()
    
    chat_prompt = (
        "💬 <b>Готов к беседе!</b>\n\n"
        "Задайте мне любой вопрос о православной вере, Писании, молитвах, духовной жизни или церковных традициях.\n\n"
        "Я отвечу понятно, с опорой на православное учение.\n\n"
        "Также можете использовать команду /dukhovnik в любой момент."
    )
    
    await query.message.answer(chat_prompt, parse_mode='HTML')
    logging.info(f"Пользователь {query.from_user.id} начал беседу через онбординг")


@router.callback_query(F.data == "show_calendar")
async def show_calendar_from_onboarding_handler(query: CallbackQuery, bot: Bot):
    """
    Обработчик кнопки "Посмотреть календарь" из онбординга.
    Отправляет информацию о календаре и предлагает попробовать команду.
    """
    await query.answer()
    
    calendar_info = (
        "🗓️ <b>Православный календарь</b>\n\n"
        "Используйте команду /calendar чтобы узнать:\n"
        "• Какой сегодня церковный праздник\n"
        "• Пост или нет\n"
        "• Чьи сегодня именины\n"
        "• Евангельское чтение дня\n\n"
        "Попробуйте прямо сейчас: /calendar"
    )
    
    await query.message.answer(calendar_info, parse_mode='HTML')
    logging.info(f"Пользователь {query.from_user.id} запросил календарь через онбординг")


@router.message(Command("stats"))
async def stats_handler(message: Message, bot: Bot):
    """
    Команда для просмотра статистики (только для администратора).
    Показывает аналитику по источникам трафика, конверсии и активности.
    """
    user_id = message.from_user.id
    
    # Проверяем, является ли пользователь администратором
    if str(user_id) != str(ADMIN_ID):
        await message.answer("❌ Эта команда доступна только администратору.")
        logging.warning(f"Попытка доступа к /stats от неавторизованного пользователя {user_id}")
        return
    
    logging.info(f"Админ {user_id} запросил статистику /stats")
    
    # Импортируем функции для проверки статусов
    from core.subscription_checker import is_free_period_active, is_trial_active, is_subscription_active
    
    # Собираем статистику
    total_users = len(user_db)
    
    # Статистика по источникам
    utm_sources = {}
    utm_campaigns = {}
    referrals_count = 0
    users_with_free_period = 0
    users_with_trial = 0
    users_with_subscription = 0
    users_onboarded = 0
    
    # Конверсии по источникам
    source_conversions = {}  # {source: {'total': N, 'free_activated': N, 'paid': N}}
    
    for uid, data in user_db.items():
        # Источники
        source = data.get('utm_source', 'unknown')
        campaign = data.get('utm_campaign', 'none')
        
        # Подсчет по источникам
        utm_sources[source] = utm_sources.get(source, 0) + 1
        
        # Подсчет по кампаниям
        if campaign and campaign != 'none':
            utm_campaigns[campaign] = utm_campaigns.get(campaign, 0) + 1
        
        # Инициализация конверсий по источникам
        if source not in source_conversions:
            source_conversions[source] = {'total': 0, 'free_activated': 0, 'trial_activated': 0, 'paid': 0}
        
        source_conversions[source]['total'] += 1
        
        # Рефералы
        if data.get('referrer_id'):
            referrals_count += 1
        
        # Активации
        if data.get('free_period_start'):
            users_with_free_period += 1
            source_conversions[source]['free_activated'] += 1
        
        if data.get('trial_start_date'):
            users_with_trial += 1
            source_conversions[source]['trial_activated'] += 1
        
        if data.get('subscription_end_date'):
            users_with_subscription += 1
            source_conversions[source]['paid'] += 1
        
        if data.get('onboarded'):
            users_onboarded += 1
    
    # Формируем текст статистики
    stats_text = "📊 <b>СТАТИСТИКА БОТА</b>\n\n"
    
    # Общая статистика
    stats_text += "━━━━━━━━━━━━━━━━━━━━━\n"
    stats_text += "<b>📈 ОБЩИЕ ПОКАЗАТЕЛИ:</b>\n"
    stats_text += f"👥 Всего пользователей: <b>{total_users}</b>\n"
    stats_text += f"✅ Прошли онбординг: <b>{users_onboarded}</b> ({users_onboarded*100//total_users if total_users else 0}%)\n"
    stats_text += f"🎁 Активировали бесплатный период: <b>{users_with_free_period}</b>\n"
    stats_text += f"🆓 Активировали триал: <b>{users_with_trial}</b>\n"
    stats_text += f"💳 Оплатили подписку: <b>{users_with_subscription}</b>\n"
    stats_text += f"🔗 Пришли по рефералке: <b>{referrals_count}</b>\n"
    
    # Конверсия в платных (определяем до использования)
    paid_conversion = 0.0
    if total_users > 0:
        paid_conversion = (users_with_subscription * 100) / total_users
        stats_text += f"📊 Конверсия в платных: <b>{paid_conversion:.2f}%</b>\n"
    else:
        stats_text += f"📊 Конверсия в платных: <b>0.00%</b> (нет пользователей)\n"
    
    # Источники трафика
    stats_text += "\n━━━━━━━━━━━━━━━━━━━━━\n"
    stats_text += "<b>🌐 ИСТОЧНИКИ ТРАФИКА:</b>\n\n"
    
    # Сортируем источники по количеству пользователей
    sorted_sources = sorted(utm_sources.items(), key=lambda x: x[1], reverse=True)
    
    for source, count in sorted_sources:
        percentage = (count * 100) / total_users if total_users else 0
        stats_text += f"📍 <b>{source}</b>: {count} ({percentage:.1f}%)\n"
        
        # Конверсии по этому источнику
        conv = source_conversions.get(source, {})
        free_conv = (conv.get('free_activated', 0) * 100) / count if count else 0
        paid_conv = (conv.get('paid', 0) * 100) / count if count else 0
        
        stats_text += f"   └ Активировали бесплатный период: {conv.get('free_activated', 0)} ({free_conv:.1f}%)\n"
        stats_text += f"   └ Оплатили подписку: {conv.get('paid', 0)} ({paid_conv:.1f}%)\n\n"
    
    # Кампании
    if utm_campaigns:
        stats_text += "━━━━━━━━━━━━━━━━━━━━━\n"
        stats_text += "<b>🎯 АКТИВНЫЕ КАМПАНИИ:</b>\n\n"
        
        sorted_campaigns = sorted(utm_campaigns.items(), key=lambda x: x[1], reverse=True)
        
        for campaign, count in sorted_campaigns[:10]:  # Топ-10 кампаний
            percentage = (count * 100) / total_users if total_users else 0
            stats_text += f"• <b>{campaign}</b>: {count} ({percentage:.1f}%)\n"
    
    # Топ-рефереры
    top_referrers = []
    for uid, data in user_db.items():
        referral_count = data.get('referrals', 0)
        if referral_count > 0:
            username = data.get('username', 'no_username')
            top_referrers.append((uid, username, referral_count))
    
    if top_referrers:
        top_referrers.sort(key=lambda x: x[2], reverse=True)
        stats_text += "\n━━━━━━━━━━━━━━━━━━━━━\n"
        stats_text += "<b>🏆 ТОП-5 РЕФЕРЕРОВ:</b>\n\n"
        
        for i, (uid, username, count) in enumerate(top_referrers[:5], 1):
            stats_text += f"{i}. @{username} (ID: {uid}): <b>{count}</b> рефералов\n"
    
    # Рекомендации
    stats_text += "\n━━━━━━━━━━━━━━━━━━━━━\n"
    stats_text += "<b>💡 РЕКОМЕНДАЦИИ:</b>\n\n"
    
    if paid_conversion < 5:
        stats_text += "⚠️ Конверсия в платных подписчиков низкая. Рекомендуется:\n"
        stats_text += "   • Усилить напоминания о подписке\n"
        stats_text += "   • Добавить уникальные функции для платных\n"
        stats_text += "   • Провести акцию со скидкой\n\n"
    
    # Определяем лучший источник по конверсии
    if source_conversions:
        best_source = max(source_conversions.items(), 
                         key=lambda x: x[1].get('paid', 0) / x[1].get('total', 1))
        stats_text += f"🎯 Лучший источник по платным: <b>{best_source[0]}</b>\n"
        stats_text += f"   Рекомендуется увеличить инвестиции в этот канал\n"
    
    # Отправляем статистику
    await message.answer(stats_text, parse_mode='HTML')
    logging.info(f"Статистика отправлена админу {user_id}")

@router.message(Command("new_chat"))
async def new_chat_handler(message: Message):
    """
    Обработчик команды /new_chat для начала новой беседы (очистка истории диалога).
    """
    user_id = message.from_user.id
    user_data = get_user(user_id)
    
    # Очищаем историю диалога
    user_data['conversation_history'] = []
    user_data['last_message_time'] = None
    save_user_db()
    
    logging.info(f"Пользователь {user_id} начал новую беседу (очистил историю)")
    
    await message.answer(
        "✨ <b>Начинаем новую беседу!</b>\n\n"
        "История нашего диалога очищена. Теперь я буду отвечать без учета предыдущих сообщений.\n\n"
        "Чем могу помочь? 🙏",
        parse_mode='HTML'
    )
