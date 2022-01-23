"""Модуль машин состояний"""

from aiogram.dispatcher.filters.state import State, StatesGroup


class UserState(StatesGroup):
    """Машина состояний для управления пользователями."""

    name_for_cr = State()
    name_for_activate = State()
    name_for_del = State()
    name_for_admin = State()
