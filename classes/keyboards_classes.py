from collections import namedtuple
from dataclasses import dataclass
from typing import Union, List

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
    """Стандартное пользовательское меню"""

    mailer: str = 'White list'
    grabber: str = 'Grabber'
    joiner: str = 'Joiner'
    modifer: str = 'Modifer'

    @classmethod
    @logger.catch
    def keyboard(cls) -> 'ReplyKeyboardMarkup':
        """Возвращает кнопочки меню для канала из списка"""

        return default_keyboard().add(
            KeyboardButton(cls.mailer),
            KeyboardButton(cls.grabber),
            KeyboardButton(cls.joiner),
            # KeyboardButton(cls.modifer),
        )


@dataclass(frozen=True)
class MailerMenu(BaseMenu):
    """Mailer menu keyboard"""

    info: str = 'Информация'
    add_token: str = 'Добавить токен'
    channels: str = 'Каналы'
    start: str = 'Старт'
    main: str = 'В главное меню'

    @classmethod
    @logger.catch
    def keyboard(cls) -> 'ReplyKeyboardMarkup':
        """Возвращает кнопочки меню для канала из списка"""

        return default_keyboard().add(
            KeyboardButton(cls.info),
            KeyboardButton(cls.add_token),
            KeyboardButton(cls.channels),
            KeyboardButton(cls.start),
            KeyboardButton(cls.main),
            KeyboardButton(cls.cancel_key),
        )


@dataclass(frozen=True)
class MailerInWorkMenu(BaseMenu):
    """Mailer in work menu keyboard"""

    autoanswer: str = 'Автоответчик ВКЛ/ВЫКЛ'
    silence: str = 'Тихий режим (mute) ВКЛ/ВЫКЛ'

    @classmethod
    @logger.catch
    def keyboard(cls) -> 'ReplyKeyboardMarkup':
        """Возвращает кнопочки меню для канала из списка"""

        return default_keyboard().add(
            KeyboardButton(cls.autoanswer),
            KeyboardButton(cls.silence),
            KeyboardButton(cls.cancel_key),
        )


@dataclass(frozen=True)
class GrabberMenu(BaseMenu):
    """Grabber menu keyboard"""

    get_token: str = 'Получить токен'
    main: str = 'В главное меню'

    @classmethod
    @logger.catch
    def keyboard(cls) -> 'ReplyKeyboardMarkup':
        """Возвращает кнопочки меню для канала из списка"""

        return default_keyboard().add(
            KeyboardButton(cls.get_token),
            KeyboardButton(cls.main),
            KeyboardButton(cls.cancel_key),
        )


@dataclass(frozen=True)
class JoinerMenu(BaseMenu):
    """Grabber menu keyboard"""

    add_tokens: str = 'Добавить токены'
    main: str = 'В главное меню'

    @classmethod
    @logger.catch
    def keyboard(cls) -> 'ReplyKeyboardMarkup':
        """Возвращает кнопочки меню для канала из списка"""

        return default_keyboard().add(
            KeyboardButton(cls.add_tokens),
            KeyboardButton(cls.main),
            KeyboardButton(cls.cancel_key),
        )


@dataclass(frozen=True)
class AdminMenu(BaseMenu):
    """Админское меню"""

    add_user: str = 'Добавить пользователя'
    show_users: str = 'Список пользователей'
    delete_user: str = 'Удалить пользователя'
    activate_user: str = 'Активировать пользователя'

    @classmethod
    @logger.catch
    def keyboard(cls) -> 'ReplyKeyboardMarkup':
        """Возвращает кнопочки меню для канала из списка"""

        return default_keyboard().add(
            KeyboardButton(cls.add_user),
            KeyboardButton(cls.show_users),
            KeyboardButton(cls.delete_user),
            KeyboardButton(cls.activate_user),
            KeyboardButton(cls.cancel_key),
        )

    @classmethod
    @logger.catch
    def get_prefix(cls, prefix: str) -> str:
        """Возвращает префикс для отлова коллбэка по имени команды"""

        return {
            cls.add_user: 'adduser',
            cls.delete_user: 'deleteuser',
            cls.activate_user: 'activateuser',
        }[prefix]


@dataclass(frozen=True)
class SuperAdminMenu(AdminMenu):
    """Админское меню"""

    add_proxy: str = 'Добавить прокси'
    delete_proxy: str = 'Удалить прокси'
    show_proxies: str = 'Список прокси'
    set_max_tokens: str = 'Настроить количество токенов'

    @classmethod
    @logger.catch
    def keyboard(cls) -> 'ReplyKeyboardMarkup':
        """Возвращает кнопочки меню для канала из списка"""

        return default_keyboard().add(
            KeyboardButton(cls.add_proxy),
            KeyboardButton(cls.delete_proxy),
            KeyboardButton(cls.show_proxies),
            KeyboardButton(cls.set_max_tokens),
        )


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
class ChannelMenu(BaseMenu):
    """Меню информации"""

    delete: str = 'Удалить'
    rename: str = 'Сменить имя'
    cooldown: str = 'Кулдаун'

    @classmethod
    @logger.catch
    def keyboard(cls) -> 'ReplyKeyboardMarkup':
        """Возвращает кнопочки из списка"""

        return default_keyboard().add(
            KeyboardButton(cls.delete),
            KeyboardButton(cls.rename),
            KeyboardButton(cls.cooldown),
            KeyboardButton(cls.cancel_key),
        )


@logger.catch
def new_channel_key() -> 'InlineKeyboardMarkup':
    """"""

    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton(text="Добавить новый канал", callback_data="new_channel"),
        InlineKeyboardButton(text="Отмена", callback_data="cancel")
    )

    return keyboard


@logger.catch
def all_tokens_keyboard(all_tokens: List[namedtuple]) -> 'InlineKeyboardMarkup':
    """Возвращает список кнопок всех токенов пользователя"""

    keyboard = InlineKeyboardMarkup(row_width=1)
    if all_tokens:
        for elem in all_tokens:
            keyboard.add(InlineKeyboardButton(
                text=f'CD: {elem.cooldown // 60} - tkn: {elem.token}',
                callback_data=f"{elem.token}"))

        return keyboard


@logger.catch
def inactive_users_keyboard(users: dict) -> 'InlineKeyboardMarkup':
    """Возвращает список кнопок с пользователями"""

    keyboard = InlineKeyboardMarkup(row_width=1)
    for telegram_id, user in users.items():
        keyboard.add(InlineKeyboardButton(
            text=f"Name: {user.nick_name}  Telegram_id: {user.telegram_id}",
            callback_data=f'activate_{user.telegram_id}'))

    return keyboard
