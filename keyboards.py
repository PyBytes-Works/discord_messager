from typing import List
from collections import namedtuple

from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
)

from config import logger
from classes.menu_classes import Menu


# --------------- keyboard menu -------------------
CHANNEL_MENU: 'Menu' = Menu(delete='Удалить', rename='Сменить имя', cooldown='Кулдаун')
# --------------- end keyboard menu -------------------


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
def admin_keyboard() -> 'ReplyKeyboardMarkup':
    """Возвращает список админских кнопок"""

    keyboard = ReplyKeyboardMarkup(
        resize_keyboard=True,
        one_time_keyboard=True,
        row_width=3
    )
    keyboard.add(
        KeyboardButton("/add_user"),
        KeyboardButton("/show_users"),
        KeyboardButton("/delete_user"),
        KeyboardButton("/activate_user"),
        KeyboardButton("/cancel")
    )
    return keyboard


@logger.catch
def superadmin_keyboard() -> 'ReplyKeyboardMarkup':
    """Возвращает список админских кнопок"""

    keyboard = admin_keyboard()
    keyboard.add(
        KeyboardButton("/add_proxy"),
        KeyboardButton("/delete_proxy"),
        KeyboardButton("/show_proxies"),
        KeyboardButton("/set_max_tokens"),
    )
    return keyboard


@logger.catch
def in_work_keyboard() -> 'ReplyKeyboardMarkup':
    """Возвращает кнопочки из списка"""

    keyboard = ReplyKeyboardMarkup(
        resize_keyboard=True,
        one_time_keyboard=True,
        row_width=3
    )

    keyboard.add(
        KeyboardButton("Автоответчик ВКЛ/ВЫКЛ"),
        KeyboardButton("Тихий режим (mute) ВКЛ/ВЫКЛ"),
        KeyboardButton("Отмена"),
    )
    return keyboard


@logger.catch
def user_menu_keyboard() -> 'ReplyKeyboardMarkup':
    """Возвращает кнопочки из списка"""

    keyboard = ReplyKeyboardMarkup(
        resize_keyboard=True,
        one_time_keyboard=True,
        row_width=3
    )

    keyboard.add(
        KeyboardButton("Информация"),
        KeyboardButton("Добавить токен"),
        KeyboardButton("Каналы"),
        KeyboardButton("Старт"),
        KeyboardButton("Отмена"),
    )
    return keyboard


@logger.catch
def channel_menu_keyboard() -> 'ReplyKeyboardMarkup':
    """Возвращает кнопочки меню для канала из списка"""

    keyboard = ReplyKeyboardMarkup(
        resize_keyboard=True,
        one_time_keyboard=True,
        row_width=3
    )

    keyboard.add(
        KeyboardButton(CHANNEL_MENU.rename),
        KeyboardButton(CHANNEL_MENU.cooldown),
        KeyboardButton(CHANNEL_MENU.delete),
        KeyboardButton("Отмена"),
    )
    return keyboard


@logger.catch
def all_tokens_keyboard(all_tokens: List[namedtuple]) -> 'InlineKeyboardMarkup':
    """Возвращает список кнопок всех токенов пользователя"""

    keyboard = InlineKeyboardMarkup(row_width=1)
    if all_tokens:
        for elem in all_tokens:
            keyboard.add(InlineKeyboardButton(
                text=f'CD: {elem.cooldown // 60} - tkn: {elem.token}', callback_data=f"{elem.token}"))

        return keyboard


@logger.catch
def new_channel_key() -> 'InlineKeyboardMarkup':
    """Возвращает список кнопок всех токенов пользователя"""

    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton(text="Добавить новый канал", callback_data="new_channel"),
        InlineKeyboardButton(text="Отмена", callback_data="cancel")
    )

    return keyboard


# @logger.catch
# async def all_channels_key(channels: List[namedtuple]) -> 'InlineKeyboardMarkup':
#     """Возвращает список кнопок всех токенов пользователя"""
#
#     keyboard = InlineKeyboardMarkup(row_width=1)
#     for elem in channels:
#         keyboard.add(InlineKeyboardButton(
#             text=f"{elem.channel_name}: {elem.guild_id}/{elem.channel_id}",
#             callback_data=f"{elem.user_channel_pk}")
#         )
#
#     return keyboard


@logger.catch
def yes_no_buttons(yes_msg: str, no_msg: str) -> 'InlineKeyboardMarkup':
    """Возвращает кнопочки Да и Нет"""

    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton(text="Да", callback_data=yes_msg),
        InlineKeyboardButton(text="Нет", callback_data=no_msg)
    )

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
