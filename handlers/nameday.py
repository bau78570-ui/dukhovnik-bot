# from aiogram import Router, Bot, F
# from aiogram.filters import Command
# from aiogram.types import Message, InlineKeyboardButton, CallbackQuery
# from aiogram.utils.keyboard import InlineKeyboardBuilder
# from aiogram.fsm.context import FSMContext
# from aiogram.fsm.state import State, StatesGroup
# from core.user_database import add_nameday_person, get_nameday_persons, remove_nameday_person

# router = Router()

# # Определяем состояния для FSM
# class NamedayStates(StatesGroup):
#     waiting_for_name_to_add = State()
#     waiting_for_name_to_remove = State()

# @router.message(Command("imeniny"))
# async def nameday_menu_handler(message: Message):
#     """
#     Обработчик для команды /imeniny.
#     Отправляет сообщение с объяснением функции и кнопками.
#     """
#     text = (
#         "✨ <b>Именины</b>\n\n"
#         "Здесь вы можете управлять списком близких, для которых хотите получать напоминания о Дне Ангела. "
#         "Я буду проверять православный календарь и сообщать вам, если у кого-то из ваших близких именины завтра."
#     )

#     builder = InlineKeyboardBuilder()
#     builder.row(InlineKeyboardButton(text="➕ Добавить близкого", callback_data="add_nameday_person"))
#     builder.row(InlineKeyboardButton(text="🗑️ Удалить", callback_data="remove_nameday_person"))
#     builder.row(InlineKeyboardButton(text="📝 Мой список", callback_data="show_my_namedays"))

#     await message.answer(text, parse_mode='HTML', reply_markup=builder.as_markup())

# @router.callback_query(F.data == "add_nameday_person")
# async def add_nameday_person_callback(callback: CallbackQuery, state: FSMContext):
#     """
#     Обрабатывает нажатие на кнопку "Добавить близкого".
#     Переводит пользователя в состояние ожидания имени.
#     """
#     await callback.answer()
#     await callback.message.edit_text(
#         "Пожалуйста, введите имя близкого человека, для которого вы хотите получать напоминания об именинах:",
#         parse_mode='HTML',
#         reply_markup=InlineKeyboardBuilder().row(InlineKeyboardButton(text="Отмена", callback_data="cancel_nameday_action")).as_markup()
#     )
#     await state.set_state(NamedayStates.waiting_for_name_to_add)

# @router.message(NamedayStates.waiting_for_name_to_add)
# async def process_name_to_add(message: Message, state: FSMContext):
#     """
#     Обрабатывает введенное имя и сохраняет его.
#     """
#     user_id = message.from_user.id
#     name = message.text.strip()

#     if not name:
#         await message.answer("Имя не может быть пустым. Пожалуйста, введите имя:")
#         return

#     add_nameday_person(user_id, name)
#     await message.answer(f"Отлично! '{name}' добавлен(а) в ваш список. Я буду напоминать вам об именинах.")
#     await state.clear()
#     await nameday_menu_handler(message) # Возвращаем пользователя в меню именин

# @router.callback_query(F.data == "remove_nameday_person")
# async def remove_nameday_person_callback(callback: CallbackQuery, state: FSMContext):
#     """
#     Обрабатывает нажатие на кнопку "Удалить".
#     Показывает список имен и просит выбрать для удаления.
#     """
#     await callback.answer()
#     user_id = callback.from_user.id
#     persons = get_nameday_persons(user_id)

#     if not persons:
#         await callback.message.edit_text("Ваш список именин пуст.", parse_mode='HTML')
#         await state.clear()
#         return

#     builder = InlineKeyboardBuilder()
#     for person_name in persons:
#         builder.row(InlineKeyboardButton(text=person_name, callback_data=f"remove_this_nameday_{person_name}"))
#     builder.row(InlineKeyboardButton(text="Отмена", callback_data="cancel_nameday_action"))
#     builder.adjust(1)

#     await callback.message.edit_text(
#         "Выберите имя, которое хотите удалить из списка:",
#         parse_mode='HTML',
#         reply_markup=builder.as_markup()
#     )
#     await state.set_state(NamedayStates.waiting_for_name_to_remove)

# @router.callback_query(F.data.startswith("remove_this_nameday_"), NamedayStates.waiting_for_name_to_remove)
# async def process_remove_nameday_selection(callback: CallbackQuery, state: FSMContext):
#     """
#     Обрабатывает выбор имени для удаления.
#     """
#     await callback.answer()
#     user_id = callback.from_user.id
#     name_to_remove = callback.data.replace("remove_this_nameday_", "")

#     remove_nameday_person(user_id, name_to_remove)
#     await callback.message.edit_text(f"'{name_to_remove}' удален(а) из вашего списка именин.")
#     await state.clear()
#     # Возвращаем пользователя в меню именин
#     message = callback.message
#     message.text = "/imeniny" # Имитируем команду для вызова nameday_menu_handler
#     await nameday_menu_handler(message)

# @router.callback_query(F.data == "show_my_namedays")
# async def show_my_namedays_callback(callback: CallbackQuery, state: FSMContext):
#     """
#     Показывает текущий список близких для именин.
#     """
#     await callback.answer()
#     user_id = callback.from_user.id
#     persons = get_nameday_persons(user_id)

#     if not persons:
#         text = "Ваш список именин пуст. Нажмите '➕ Добавить близкого', чтобы начать получать напоминания."
#     else:
#         text = "<b>Ваш список близких для напоминаний об именинах:</b>\n\n" + "\n".join([f"• {name}" for name in persons])
    
#     builder = InlineKeyboardBuilder()
#     builder.row(InlineKeyboardButton(text="➕ Добавить близкого", callback_data="add_nameday_person"))
#     builder.row(InlineKeyboardButton(text="🗑️ Удалить", callback_data="remove_nameday_person"))
#     builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_nameday_menu"))

#     await callback.message.edit_text(text, parse_mode='HTML', reply_markup=builder.as_markup())
#     await state.clear() # Очищаем состояние, если оно было

# @router.callback_query(F.data == "back_to_nameday_menu")
# async def back_to_nameday_menu_callback(callback: CallbackQuery):
#     """
#     Возвращает пользователя в главное меню именин.
#     """
#     await callback.answer()
#     message = callback.message
#     message.text = "/imeniny" # Имитируем команду для вызова nameday_menu_handler
#     await nameday_menu_handler(message)

# @router.callback_query(F.data == "cancel_nameday_action")
# async def cancel_nameday_action(callback: CallbackQuery, state: FSMContext):
#     """
#     Отменяет текущее действие по добавлению/удалению имени.
#     """
#     await callback.answer("Действие отменено.", show_alert=True)
#     await state.clear()
#     message = callback.message
#     message.text = "/imeniny" # Имитируем команду для вызова nameday_menu_handler
#     await nameday_menu_handler(message)
