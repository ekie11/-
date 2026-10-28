from aiogram.fsm.state import State, StatesGroup


class FormatFlow(StatesGroup):
    waiting_input = State()
    choosing_profile = State()
    choosing_mode = State()


class GuidelineFlow(StatesGroup):
    waiting_input = State()
    choosing_base = State()
    creating = State()
    reviewing = State()
    naming = State()
