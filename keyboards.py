"""Модуль с клавиатурами и кнопками"""
from typing import List

from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
)
from models import User, Token
from config import logger


@logger.catch
def cancel_keyboard() -> 'ReplyKeyboardMarkup':
    """Возвращает кнопку 'Отмена'"""

    return ReplyKeyboardMarkup(
            resize_keyboard=True,
            one_time_keyboard=True).add(KeyboardButton("Отмена")
    )


@logger.catch
def inactive_users_keyboard(users: dict) -> 'InlineKeyboardMarkup':
    """Возвращает список кнопок с пользователями"""

    keyboard = InlineKeyboardMarkup(row_width=1)
    for telegram_id, user in users.items():
        keyboard.add(InlineKeyboardButton(text=f"Name: {user.nick_name}  Telegram_id: {user.telegram_id}", callback_data=f'activate_{user.telegram_id}'))

    return keyboard


@logger.catch
def admin_keyboard() -> 'InlineKeyboardMarkup':
    """Возвращает список админских кнопок"""
    # TODO сделать
    keyboard = InlineKeyboardMarkup(row_width=1)

    return keyboard


@logger.catch
def user_menu_keyboard() -> 'ReplyKeyboardMarkup':
    """Возвращает кнопочки из списка"""

    keyboard = ReplyKeyboardMarkup(
            resize_keyboard=True,
            one_time_keyboard=True
    )

    keyboard.row(
        KeyboardButton("/start_parsing"),
        # KeyboardButton("/stop"),
    )
    keyboard.row(
        KeyboardButton("/add_token"),
        KeyboardButton("/set_cooldown"),
        KeyboardButton("/info"),
        KeyboardButton("/cancel")
    )
    return keyboard


def all_tokens_keyboard(telegram_id: str) -> 'InlineKeyboardMarkup':
    """Возвращает список кнопок всех токенов пользователя"""

    keyboard = InlineKeyboardMarkup(row_width=1)
    all_tokens: List[dict] = Token.get_all_user_tokens(telegram_id=telegram_id)
    if all_tokens:
        for elem in all_tokens:
            token = tuple(elem.keys())[0]
            cooldown = elem[token]["cooldown"]
            keyboard.add(InlineKeyboardButton(text=f'CD: {cooldown // 60} - tkn: {token}', callback_data=f"{token}"))

        return keyboard




#
#
# @logger.catch
# def collection_menu(user: str, page_number: int, page_size: int) -> InlineKeyboardMarkup:
#     user_collections = UserCollection.get_collections(user)
#     user_collections = user_collections.get("collections", None)
#     collections_list = datastore.COLLECTIONS["collections"].keys()
#     collections_list = tuple(collections_list)
#     col_buttons = InlineKeyboardMarkup(row_width=1)
#     col_buttons.add(InlineKeyboardButton(text='Выбрать все.', callback_data=f'all_collections'))
#     col_buttons.add(InlineKeyboardButton(text='Очистить список.', callback_data=f'clear_collections'))
#     start = (page_number - 1) * page_size
#     for name in collections_list[start: start + page_size]:
#         check, postfix = (' ✅', '_d') if user_collections is not None and name in user_collections else ('', '_a')
#         col_buttons.add(InlineKeyboardButton(
#             text=f'{name}{check}', callback_data=f'{name}{postfix}')
#         )
#     col_buttons.row(
#         InlineKeyboardButton(text='👈НАЗАД', callback_data=f'nav_back'),
#         InlineKeyboardButton(text='ЗАКОНЧИТЬ👇', callback_data=f'nav_end'),
#         InlineKeyboardButton(text='ВПЕРЕД👉', callback_data=f'nav_next')
#     )
#
#     return col_buttons

#
# @logger.catch
# def get_collections_buttons(key: str) -> 'InlineKeyboardMarkup':
#     """Возвращает клавиатуру с фильтрами коллекций"""
#
#     keyboard = InlineKeyboardMarkup(row_width=1)
#
#     if key == "collections":
#         keyboard.add(
#             InlineKeyboardButton(text='Все (сбросить фильтры коллекций)', callback_data=f'{key}_all')
#         )
#     return keyboard

#
# @logger.catch
# def get_yes_no_buttons(yes_msg: str, no_msg: str) -> 'InlineKeyboardMarkup':
#     """Возвращает кнопочки Да и Нет"""
#
#     keyboard = InlineKeyboardMarkup(row_width=1)
#     keyboard.add(
#         InlineKeyboardButton(text="Да", callback_data=yes_msg),
#         InlineKeyboardButton(text="Нет", callback_data=no_msg)
#     )
#
#     return keyboard
#
#
#
# @logger.catch
# def start_stop_keys() -> 'ReplyKeyboardMarkup':
#     """Возвращает кнопочки из списка"""
#
#     keyboard = ReplyKeyboardMarkup(
#             resize_keyboard=True,
#             one_time_keyboard=True
#     )
#
#     keyboard.row(
#         KeyboardButton("/start"),
#         KeyboardButton("/stop"),
#         KeyboardButton("/filters")
#     )
#     keyboard.row(
#         KeyboardButton("/lots"),
#         KeyboardButton("/status"),
#         KeyboardButton("/type"),
#         KeyboardButton("/price"),
#     )
#
#     return keyboard
