from dataclasses import dataclass
from typing import Union

from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardRemove
)

from config import logger


def default_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        resize_keyboard=True,
        one_time_keyboard=True,
        row_width=3
    )


@dataclass(frozen=True)
class BaseMenu:
    cancel_key: str = 'Отмена'

    @classmethod
    @logger.catch
    def keyboard(cls) -> Union[ReplyKeyboardMarkup, InlineKeyboardMarkup]:
        """Возвращает кнопочку Отмена"""

        return default_keyboard().add(KeyboardButton(cls.cancel_key))


@dataclass(frozen=True)
class StartMenu(BaseMenu):
    "Стандартное пользовательское меню"

    buy_subscription: str = 'Купить подписку'
    renew_subscription: str = 'Продлить подписку'
    get_license_key: str = 'Получить лицензию'
    information: str = 'Информация'

    @classmethod
    @logger.catch
    def keyboard(cls) -> 'ReplyKeyboardMarkup':
        """Возвращает кнопочки меню для канала из списка"""

        return default_keyboard().add(
            KeyboardButton(cls.buy_subscription),
            # KeyboardButton(cls.renew_subscription),
            KeyboardButton(cls.get_license_key),
            KeyboardButton(cls.information),
            KeyboardButton(cls.cancel_key),
        )

    @classmethod
    @logger.catch
    def get_prefix(cls, prefix: str) -> str:
        """Возвращает префикс для отлова коллбэка по имени команды"""

        # TODO переписать на словар со строки!!!!
        return {
            cls.renew_subscription: 'renew',
            cls.buy_subscription: 'buy',
            cls.get_license_key: 'generatelicense',
        }[prefix]


@dataclass(frozen=True)
class AdminMenu(BaseMenu):
    """Админское меню"""

    admin: str = 'admin'
    add_product: str = 'Добавить товар'
    delete_product: str = 'Удалить товар'
    set_user_admin: str = 'Назначить админа'
    set_channel: str = 'Добавить канал'

    @classmethod
    @logger.catch
    def keyboard(cls) -> 'ReplyKeyboardMarkup':
        """Возвращает кнопочки меню для канала из списка"""

        return default_keyboard().add(
            KeyboardButton(cls.add_product),
            KeyboardButton(cls.delete_product),
            KeyboardButton(cls.set_user_admin),
            KeyboardButton(cls.set_channel),
            KeyboardButton(cls.cancel_key),
        )

    @classmethod
    @logger.catch
    def get_prefix(cls, prefix: str) -> str:
        """Возвращает префикс для отлова коллбэка по имени команды"""

        return {
            cls.add_product: 'addproduct',
            cls.delete_product: 'deleteproduct',
        }[prefix]


@dataclass
class YesNo:

    @classmethod
    @logger.catch
    def keyboard(
            cls,
            prefix: str,
            suffix: str,
            cancel_callback: str = BaseMenu.cancel_key,
            yes_key: str = 'Да',
            no_key: str = BaseMenu.cancel_key,
            splitter: str = '_'
    ) -> 'InlineKeyboardMarkup':
        """Возвращает кнопочку Отмена"""

        return InlineKeyboardMarkup(row_width=2
        ).add(
            InlineKeyboardButton(text=yes_key, callback_data=f'{prefix}{splitter}{suffix}')
        ).add(
            InlineKeyboardButton(text=no_key, callback_data=cancel_callback)
        )


@dataclass(frozen=True)
class InformationMenu(BaseMenu):
    """Меню информации"""

    balance: str = 'Баланс'
    licenses: str = 'Лицензии'

    @classmethod
    @logger.catch
    def keyboard(cls) -> 'ReplyKeyboardMarkup':
        """Возвращает кнопочки из списка"""

        return default_keyboard().add(
            KeyboardButton(cls.balance),
            KeyboardButton(cls.licenses),
            KeyboardButton(cls.cancel_key),
        )
