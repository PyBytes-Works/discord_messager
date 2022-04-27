"""Модуль машин состояний"""

from aiogram.dispatcher.filters.state import State, StatesGroup


class UserStates(StatesGroup):
    """Машина состояний для управления пользователями."""
    in_work = State()


class AdminStates(StatesGroup):

    name_for_activate = State()
    name_for_admin = State()
    user_add_proxy = State()
    user_delete_proxy = State()
    user_delete_all_proxy = State()
    name_for_del = State()
    user_add_token = State()
    user_activate = State()
    user_set_max_tokens = State()


class LogiStates(StatesGroup):
    add_new_user = State()
    add_new_user_expiration = State()
    add_new_user_max_tokens = State()


class TokenStates(StatesGroup):
    select_channel = State()
    create_channel = State()
    add_token = State()
    check_token = State()
    add_channel_cooldown = State()
    delete_token = State()
    select_token = State()
    set_name_for_token = State()


class UserChannelStates(StatesGroup):
    select_user_channel_to_rename = State()
    enter_name_for_user_channel = State()
    delete_for_user_channel = State()
    checks_tokens_for_user_channel = State()
