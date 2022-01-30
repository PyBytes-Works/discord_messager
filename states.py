"""Модуль машин состояний"""

from aiogram.dispatcher.filters.state import State, StatesGroup


class UserState(StatesGroup):
    """Машина состояний для управления пользователями."""
    user_wait_message = State()
    user_add_token = State()
    user_add_channel = State()
    user_add_proxy = State()
    user_add_language = State()
    user_start_game = State()
