from collections import namedtuple

from aiogram.dispatcher.filters import Text
from aiogram.types import Message
from aiogram.dispatcher import FSMContext

from classes.db_interface import DBI
from classes.errors_reporter import ErrorsReporter
from classes.keyboards_classes import BaseMenu, StartMenu, AdminMenu
from config import logger, Dispatcher
from decorators.checkers import check_is_admin
from states import LoginState
from utils import check_is_int


@check_is_admin
@logger.catch
async def start_add_new_user_handler(message: Message) -> None:
    """Получает сообщение от админа и добавляет пользователя в БД"""

    await message.answer(
        "Перешлите (forward) мне любое сообщение пользователя, "
        "которого вы хотите добавить или активировать.",
        reply_markup=BaseMenu.keyboard()
    )
    await LoginState.add_new_user.set()


@logger.catch
async def check_new_user_is_exists_handler(message: Message, state: FSMContext) -> None:
    """Получает сообщение от админа и добавляет пользователя в БД

    """
    logger.debug(f"Add user message: {message}")
    if not message.forward_from:
        await message.answer(
            "Нужно переслать (forward) любое сообщение из телеграма от пользователя, "
            "которого вы хотите добавить. Если не получается - скажите пользователю, "
            "чтоб разрешил пересылку сообшений в своих настройках телеграма.",
            reply_markup=BaseMenu.keyboard()
        )
        return

    new_user_telegram_id: str = str(message.forward_from.id)
    new_user_nickname: str = message.forward_from.username
    await message.answer(
        f"Выбран пользователь {new_user_telegram_id}: {new_user_nickname}",
        reply_markup=BaseMenu.keyboard()
    )
    await state.update_data(
        new_user_telegram_id=new_user_telegram_id, new_user_nickname=new_user_nickname
    )
    if await DBI.get_user_by_telegram_id(telegram_id=new_user_telegram_id):
        await message.answer("Пользователь существует и будет перезаписан."
                             "\nВсе его токены и каналы будут удалены.")
    text: str = f"Введите количество токенов для пользователя {new_user_nickname}:"
    await message.answer(text, reply_markup=BaseMenu.keyboard())
    await LoginState.add_new_user_max_tokens.set()


@logger.catch
async def set_max_tokens_for_new_user_handler(message: Message, state: FSMContext) -> None:
    """Проверка максимального количества токенов и запрос на введение имени нового пользователя"""

    max_tokens: int = check_is_int(message.text)
    if not max_tokens:
        await message.answer(
            'Число должно быть целым положительным. Введите еще раз: ',
            reply_markup=BaseMenu.keyboard()
        )
        return
    await state.update_data(max_tokens=max_tokens)
    await message.answer('Введите время подписки в ЧАСАХ:: ', reply_markup=BaseMenu.keyboard())
    await LoginState.add_new_user_expiration.set()


@logger.catch
async def check_expiration_and_add_new_user_handler(message: Message, state: FSMContext) -> None:
    """Проверка введенного времени подписки и создание токена для нового пользователя"""

    subscribe_time: int = check_is_int(message.text)
    if message.text == "-1":
        subscribe_time: int = -1
    hours_in_year: int = 8760
    if not subscribe_time or subscribe_time > hours_in_year * 2:
        await message.answer(
            'Время в часах должно быть целым положительным. '
            '\nВведите еще раз время подписки в ЧАСАХ: ',
            reply_markup=BaseMenu.keyboard()
        )
        return
    state_data: dict = await state.get_data()
    new_user_telegram_id: str = state_data["new_user_telegram_id"]
    new_user_nickname: str = state_data["new_user_nickname"]
    max_tokens: int = state_data["max_tokens"]
    proxy: namedtuple = await DBI.get_low_used_proxy()
    if not proxy or not proxy.proxy_pk:
        await ErrorsReporter.send_report_to_admins(text="Нет проксей.")
    user_data: dict = {
        "telegram_id": new_user_telegram_id,
        "nick_name": new_user_nickname,
        "max_tokens": max_tokens,
        "expiration": subscribe_time,
        "proxy_pk": proxy.proxy_pk
    }
    text: str = (
        f"Новый пользователь добавлен в БД: "
        f"\nИмя: {new_user_nickname}  ID:{new_user_telegram_id}"
        f"\nМаксимум токенов: {max_tokens}"
        f"\nДобавлен на срок (в часах): {subscribe_time}"
        f"\nПрокси: {proxy.proxy}"
    )
    if await DBI.get_user_by_telegram_id(telegram_id=new_user_telegram_id):
        await DBI.reactivate_user(**user_data)
        await message.answer("Пользователь активирован.", reply_markup=StartMenu.keyboard())
        await state.finish()
        return

    if not await DBI.add_new_user(**user_data):
        text: str = (f"ОШИБКА ДОБАВЛЕНИЯ ПОЛЬЗОВАТЕЛЯ В БД: "
                     f"\nИмя: {new_user_nickname}  ID:{new_user_telegram_id}")
        await ErrorsReporter.send_report_to_admins(text)
        await message.answer(text)
        logger.error(text)
        await state.finish()
        return
    await message.answer(text, reply_markup=StartMenu.keyboard())
    logger.admin(
        f"Admin: {message.from_user.username}: {message.from_user.id} "
        f"добавил пользователя {new_user_nickname}: {new_user_telegram_id}"
        f"\tТокенов: [{max_tokens}]"
        f"\tВремя подписки (в часах): {subscribe_time}"
    )
    await ErrorsReporter.send_message_to_user(
        text="Вы добавлены в базу данных.",
        telegram_id=new_user_telegram_id,
        keyboard=StartMenu.keyboard())
    await state.finish()


@logger.catch
def login_register_handlers(dp: Dispatcher) -> None:
    """
    Регистратор для функций данного модуля
    """
    dp.register_message_handler(start_add_new_user_handler, Text(
        equals=[AdminMenu.add_user, AdminMenu.activate_user, '/add_user', '/activate_user']))
    dp.register_message_handler(check_new_user_is_exists_handler, state=LoginState.add_new_user)
    dp.register_message_handler(set_max_tokens_for_new_user_handler, state=LoginState.add_new_user_max_tokens)
    dp.register_message_handler(check_expiration_and_add_new_user_handler, state=LoginState.add_new_user_expiration)
