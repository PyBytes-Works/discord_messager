"""Модуль машин состояний"""

from aiogram.dispatcher.filters.state import State, StatesGroup


class UserState(StatesGroup):
    """Машина состояний для управления пользователями."""

    user_wait_message = State()
