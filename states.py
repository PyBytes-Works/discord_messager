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
    name_for_cr = State()
    name_for_del = State()
    name_for_activate = State()
    name_for_admin = State()
    max_tokens_req = State()
