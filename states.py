"""Модуль машин состояний"""

from aiogram.dispatcher.filters.state import State, StatesGroup


class UserState(StatesGroup):
    """Машина состояний для управления пользователями."""
    user_wait_message = State()
    user_add_cooldown = State()
    user_add_token = State()
    user_add_channel = State()
    user_add_proxy = State()
    user_delete_proxy = State()
    user_add_discord_id = State()
    user_add_language = State()
    user_delete_token = State()
    user_start_game = State()
    user_set_max_tokens = State()
    user_activate = State()
    name_for_cr = State()
    name_for_del = State()
    name_for_activate = State()
    name_for_admin = State()
    max_tokens_req = State()
    set_user_self_cooldown = State()
    select_token = State()
    subscribe_time = State()
    answer_to_reply = State()
    in_work = State()
    user_delete_all_proxy = State()


class AdminStates(StatesGroup):
    add_new_user = State()
    add_new_user_expiration = State()
    add_new_user_max_tokens = State()


class TokenStates(StatesGroup):
    select_channel = State()
    create_channel = State()
    add_token = State()
    check_token = State()
    add_channel_cooldown = State()
