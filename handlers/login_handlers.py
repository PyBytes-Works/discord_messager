from collections import namedtuple

from aiogram.types import Message
from aiogram.dispatcher import FSMContext

from utils import check_is_int, send_report_to_admins
from classes.db_interface import DBI
from config import logger, Dispatcher, admins_list
from keyboards import user_menu_keyboard, cancel_keyboard
from states import AdminStates


@logger.catch
async def start_add_new_user_handler(message: Message) -> None:
    """Получает сообщение от админа и добавляет пользователя в БД"""

    telegram_id: str = str(message.from_user.id)
    user_is_admin: bool = telegram_id in admins_list
    user_is_superadmin: bool = await DBI.is_admin(telegram_id)
    if user_is_admin or user_is_superadmin:
        await message.answer(
            "Перешлите (forward) мне любое сообщение от пользователя, которого вы хотите добавить.",
            reply_markup=cancel_keyboard()
        )
        await AdminStates.add_new_user.set()


@logger.catch
async def check_new_user_is_exists_handler(message: Message, state: FSMContext) -> None:
    """Получает сообщение от админа и добавляет пользователя в БД

    """
    if not message.forward_from:
        await message.answer(
            "Нужно переслать (forward) любое сообщение из телеграма от пользователя, "
            "которого вы хотите добавить.",
            reply_markup=user_menu_keyboard()
        )
        return

    new_user_telegram_id: str = str(message.forward_from.id)
    new_user_nickname: str = message.forward_from.username
    await message.answer(
        f"В базу будет добавлен пользователь {new_user_telegram_id}: {new_user_nickname}",
        reply_markup=user_menu_keyboard()
    )
    if await DBI.get_user_by_telegram_id(telegram_id=new_user_telegram_id):
        text: str = f"Пользователь {new_user_telegram_id}: {new_user_nickname} уже существует."
        await message.answer(text, reply_markup=user_menu_keyboard())
        await state.finish()
        return
    await state.update_data(
        new_user_telegram_id=new_user_telegram_id, new_user_nickname=new_user_nickname
    )
    text: str = f"Введите количество токенов для пользователя {new_user_nickname}:"
    await message.answer(text, reply_markup=user_menu_keyboard())
    await AdminStates.add_new_user_max_tokens.set()


@logger.catch
async def set_max_tokens_for_new_user_handler(message: Message, state: FSMContext) -> None:
    """Проверка максимального количества токенов и запрос на введение имени нового пользователя"""

    max_tokens: int = check_is_int(message.text)
    if not max_tokens:
        await message.answer(
            'Число должно быть целым положительным. Введите еще раз: ',
            reply_markup=cancel_keyboard()
        )
        return
    await state.update_data(max_tokens=max_tokens)
    await message.answer('Введите время подписки в ЧАСАХ:: ', reply_markup=cancel_keyboard())
    await AdminStates.add_new_user_expiration.set()


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
            reply_markup=cancel_keyboard()
        )
        return
    state_data: dict = await state.get_data()
    new_user_telegram_id: str = state_data["new_user_telegram_id"]
    new_user_nickname: str = state_data["new_user_nickname"]
    max_tokens: int = state_data["max_tokens"]
    proxy: namedtuple = await DBI.get_low_used_proxy()
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
    )
    if not await DBI.add_new_user(**user_data):
        text: str = (f"ОШИБКА ДОБАВЛЕНИЯ ПОЛЬЗОВАТЕЛЯ В БД: "
                     f"\nИмя: {new_user_nickname}  ID:{new_user_telegram_id}")
        await send_report_to_admins(text)
    await message.answer(text, reply_markup=user_menu_keyboard())
    await state.finish()


@logger.catch
def login_register_handlers(dp: Dispatcher) -> None:
    """
    Регистратор для функций данного модуля
    """
    dp.register_message_handler(start_add_new_user_handler, commands=['add_user'])
    dp.register_message_handler(check_new_user_is_exists_handler, state=AdminStates.add_new_user)
    dp.register_message_handler(set_max_tokens_for_new_user_handler, state=AdminStates.add_new_user_max_tokens)
    dp.register_message_handler(check_expiration_and_add_new_user_handler, state=AdminStates.add_new_user_expiration)
