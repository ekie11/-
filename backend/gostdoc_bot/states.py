from aiogram.fsm.state import State, StatesGroup


class FormatFlow(StatesGroup):
    waiting_input = State()
    choosing_profile = State()
    choosing_mode = State()
