from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, InlineKeyboardButton
from datetime import datetime
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext # Импортируем FSMContext
from core.content_library import reading_plans
from core.content_sender import send_and_delete_previous # Импортируем новую централизованную функцию
from core.user_database import set_prayer_topic
from states import PrayerState # Импортируем состояния

# Создаем роутер для обработки callback-ов
router = Router()

@router.callback_query(F.data.startswith("prayer_topic:"))
async def prayer_topic_selection_handler(callback: CallbackQuery, bot: Bot, state: FSMContext):
    """
    Обрабатывает выбор темы молитвы и устанавливает состояние FSM.
    """
    topic_key = callback.data.split(":")[1]
    
    topics_map = {
        "health": "О здоровье",
        "work": "В делах",
        "family": "О семье",
        "custom": "Своими словами",
        "daily_word_reflection": "О Слове Дня"
    }
    
    prompts_map = {
        "health": "Понимаю. Напиши, о чьем здоровье ты хочешь помолиться (например, 'о моем' или 'о здравии близкого тебе человека')?",
        "work": "Отлично! Напиши, подробнее о каком деле или начинании ты просишь Божьей помощи?",
        "family": "Семья — это дар Божий. Напиши, о ком из близких или о какой семейной нужде ты хочешь помолиться?",
        "custom": "Господь слышит каждое слово, идущее от сердца. Напиши своими словами, что у тебя на душе, и я помогу облечь это в молитву.",
        "daily_word_reflection": "Напиши, как ты хотел бы помолиться, основываясь на сегодняшнем Слове Дня."
    }

    topic_text = topics_map.get(topic_key)
    prompt_text = prompts_map.get(topic_key)

    if not topic_text or not prompt_text:
        await callback.answer("Произошла ошибка при выборе темы молитвы.", show_alert=True)
        return

    # Сначала сохраняем состояние — так оно не потеряется при сбое редактирования
    await state.set_state(PrayerState.waiting_for_details)
    await state.update_data(prayer_topic=topic_text)

    try:
        if callback.message.photo:
            await callback.message.edit_caption(
                caption=prompt_text,
                parse_mode='HTML'
            )
        else:
            await callback.message.edit_text(
                text=prompt_text,
                parse_mode='HTML'
            )
    except Exception as e:
        import logging
        logging.warning(f"Не удалось отредактировать сообщение при выборе темы молитвы {topic_key}: {e}")
        # Отправляем новый текст, если редактирование не удалось
        await callback.message.answer(prompt_text, parse_mode='HTML')
    await callback.answer()


# Словарь для сопоставления ключей планов и их названий
# plan_key_map = {
#     "bible_plan_7": ("7_days_of_peace", "7 дней к покою и смирению"),
#     "bible_plan_14": ("14_days_of_faith", "14 дней для веры и любви"),
#     "bible_plan_21": ("21_days_of_forgiveness", "Путь познания за 21 день")
# }

# @router.callback_query(F.data.startswith("bible_plan_"))
# async def process_bible_plan_selection(callback: CallbackQuery, bot: Bot):
#     """
#     Обрабатывает выбор плана чтения Библии и отправляет первый день.
#     """
#     plan_key, plan_title = plan_key_map.get(callback.data)
    
#     if not plan_key or not reading_plans[plan_key]:
#         await callback.answer("Этот план чтения пока не готов.", show_alert=True)
#         return

#     # Отправляем или редактируем сообщение с первым днем плана
#     await send_or_edit_day_content(callback, bot, plan_key, 0)


# @router.callback_query(F.data == "back_to_plans")
# async def back_to_plans_handler(callback: CallbackQuery):
#     """
#     Возвращает пользователя к списку планов чтения.
#     """
#     text = ("📖 <b>Путь к Свету: Изучение Библии</b>\n\n"
#             "Библия — это слово Бога, адресованное лично вам! "
#             "Выберите программу чтения, которая больше всего отзывается в вашем сердце и удобна вам по времени.")
    
#     builder = InlineKeyboardBuilder()
#     builder.row(InlineKeyboardButton(text="7 дней к покою и смирению", callback_data="bible_plan_7"))
#     builder.row(InlineKeyboardButton(text="14 дней для веры и любви", callback_data="bible_plan_14"))
#     builder.row(InlineKeyboardButton(text="Путь познания за 21 день", callback_data="bible_plan_21"))

#     await callback.message.edit_caption(caption=text, reply_markup=builder.as_markup(), parse_mode='HTML')
#     await callback.answer()


# @router.callback_query(F.data.startswith("nav_day_"))
# async def navigate_reading_day(callback: CallbackQuery, bot: Bot):
#     """
#     Обрабатывает навигацию по дням плана чтения.
#     """
#     _, _, plan_key, day_index_str = callback.data.split("_")
#     day_index = int(day_index_str)

#     await send_or_edit_day_content(callback, bot, plan_key, day_index)


# async def send_or_edit_day_content(callback: CallbackQuery, bot: Bot, plan_key: str, day_index: int):
#     """
#     Отправляет или редактирует сообщение с контентом определенного дня плана.
#     """
#     plan_title = next((title for cb, (key, title) in plan_key_map.items() if key == plan_key), "План чтения")
#     plan_content = reading_plans.get(plan_key, [])
    
#     if not 0 <= day_index < len(plan_content):
#         await callback.answer("Вы завершили этот план чтения! Поздравляем!", show_alert=True)
#         return

#     day_content = plan_content[day_index]
#     text = (
#         f"<b>{plan_title}. {day_content['title']}</b>\n\n"
#         f"📖 <i>{day_content['scripture']}</i>\n\n"
#         f"{day_content['reflection']}"
#     )

#     builder = InlineKeyboardBuilder()
#     # Кнопка "Назад" доступна если это не первый день
#     prev_day_button = InlineKeyboardButton(text="⬅️ Предыдущий день", callback_data=f"nav_day_{plan_key}_{day_index - 1}")
#     # Кнопка "Вперед" доступна если это не последний день
#     next_day_button = InlineKeyboardButton(text="➡️ Следующий день", callback_data=f"nav_day_{plan_key}_{day_index + 1}")
    
#     nav_buttons = []
#     if day_index > 0:
#         nav_buttons.append(prev_day_button)
#     if day_index < len(plan_content) - 1:
#         nav_buttons.append(next_day_button)
        
#     builder.row(*nav_buttons)
#     builder.row(InlineKeyboardButton(text="◀️ К списку планов", callback_data="back_to_plans"))

#     # Если это первый вызов (не редактирование), удаляем старое и отправляем новое
#     if isinstance(callback.message.reply_markup.inline_keyboard[0][0], InlineKeyboardButton) and "bible_plan_" in callback.message.reply_markup.inline_keyboard[0][0].callback_data:
#         await callback.message.delete() # Закомментировано согласно заданию
#         await send_content_message(
#             bot=bot,
#             chat_id=callback.message.chat.id,
#             text=text,
#             image_name='bible_study.png',
#             reply_markup=builder.as_markup()
#         )
#     else: # Иначе редактируем существующее
#         await callback.message.edit_caption(caption=text, reply_markup=builder.as_markup(), parse_mode='HTML')

#     await callback.answer()


# @router.callback_query(F.data == "fasting_recipe_of_the_day")
# async def process_fasting_recipe(callback: CallbackQuery):
#     """
#     Обрабатывает нажатие на кнопку "Постный рецепт дня".
#     """
#     from core.content_library import fasting_content
#     # Пока берем 'day_1' как пример
#     content = fasting_content.get('day_1')
#     if content:
#         text = f"🍽️ <b>{content['day_title']}</b>\n\n<b>Рецепт:</b>\n{content['recipe']}"
#         await callback.message.edit_caption(caption=text, reply_markup=None, parse_mode='HTML')
#     await callback.answer()


# @router.callback_query(F.data == "fasting_thought_of_the_day")
# async def process_fasting_thought(callback: CallbackQuery):
#     """
#     Обрабатывает нажатие на кнопку "Мысль на время поста".
#     """
#     from core.content_library import fasting_content
#     # Пока берем 'day_1' как пример
#     content = fasting_content.get('day_1')
#     if content:
#         text = f"💡 <b>{content['day_title']}</b>\n\n<b>Мысль дня:</b>\n{content['thought']}"
#         await callback.message.edit_caption(caption=text, reply_markup=None, parse_mode='HTML')
#     await callback.answer()
