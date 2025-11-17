from aiogram.fsm.state import State, StatesGroup

class PrayerState(StatesGroup):
    """
    Состояния для Молитвенного Помощника.
    """
    waiting_for_details = State()
