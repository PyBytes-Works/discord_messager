"""Модуль для обработчиков администратора"""

from collections import namedtuple
import re
from typing import Tuple

import aiogram
import aiogram.utils.exceptions
from aiogram import Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove, InlineKeyboardMarkup, \
    InlineKeyboardButton

from classes.vocabulary import Vocabulary
from config import logger, bot, admins_list
from handlers.main_handlers import message_cancel_handler
from keyboards import cancel_keyboard, user_menu_keyboard, inactive_users_keyboard, admin_keyboard, \
    superadmin_keyboard
from states import AdminStates
from classes.db_interface import DBI
from classes.errors_sender import ErrorsSender
from utils import check_is_int


@logger.catch
async def send_message_to_all_users_handler(message: Message) -> None:
    """Обработчик команд /sendall, /su"""

    index: int = 0
    text: str = message.text
    if text.startswith("/sendall"):
        index = 9
    elif text.startswith("/sa"):
        index = 4
    data: str = f'[Рассылка][Всем]: {text[index:]}'
    user_id: str = str(message.from_user.id)
    if not data:
        await message.answer("Нет данных для отправки.")
        return
    if user_id in admins_list:
        for user in await DBI.get_active_users():
            try:
                await bot.send_message(chat_id=user, text=data)
            except aiogram.utils.exceptions.ChatNotFound as err:
                logger.error(f"Не смог отправить сообщение пользователю {user}.", err)
            except aiogram.utils.exceptions.BotBlocked as err:
                logger.error(f"Пользователь {user} заблокировал бота", err)
                result: bool = await DBI.deactivate_user(telegram_id=user)
                if result:
                    await ErrorsSender.send_report_to_admins(
                        f"Пользователь {user} заблокировал бота. "
                        f"\nЕго аккаунт деактивирован.")


@logger.catch
async def request_max_tokens_handler(message: Message) -> None:
    """Обработчик команды /set_max_tokens"""

    user_telegram_id: str = str(message.from_user.id)
    user_is_admin: bool = await DBI.is_admin(telegram_id=user_telegram_id)
    user_is_superadmin: bool = user_telegram_id in admins_list
    if user_is_admin or user_is_superadmin:
        await message.answer(
            'Введите telegram_id пользователя и количество токенов через пробел. '
            '\nПример: "3333333 10"',
            reply_markup=cancel_keyboard()
        )
        await AdminStates.user_set_max_tokens.set()


@logger.catch
async def set_max_tokens_handler(message: Message, state: FSMContext) -> None:
    """Проверка и запись в БД нового количества токенов для пользователя"""

    telegram_id = str(message.text.strip().split()[0])
    new_tokens_count: int = check_is_int(message.text.strip().split()[-1])
    if new_tokens_count and telegram_id:
        if await DBI.set_max_tokens(telegram_id=telegram_id, max_tokens=new_tokens_count):
            await message.answer(
                f'Для пользователя {telegram_id} установили количество токенов {new_tokens_count}',
                reply_markup=user_menu_keyboard()
            )
        else:
            text = (
               "F: set_max_tokens_handler: Не изменилось количество токенов пользователя."
               f"\nУбедитесь, что пользователь с {telegram_id} существует."
            )
            logger.error(text)
            await message.answer(text, reply_markup=ReplyKeyboardRemove())
        await state.finish()
    else:
        await message.answer(
            f'Введеные неверные данные.'
            f'Введите telegram_id пользователя и количество токенов через пробел без кавычек'
            '\nПример: "3333333 10"',
            reply_markup=cancel_keyboard()
        )
        return


@logger.catch
async def request_proxies_handler(message: Message) -> None:
    """Обработчик команды /add_proxy /delete_proxy, /delete_all_proxy"""

    user_telegram_id: str = str(message.from_user.id)
    user_is_superadmin: bool = user_telegram_id in admins_list
    if user_is_superadmin:
        await message.answer(
            'Введите прокси в формате "123.123.123.123:5555" (можно несколько через пробел)',
            reply_markup=cancel_keyboard()
        )
        if message.text == '/add_proxy':
            await AdminStates.user_add_proxy.set()
        elif message.text == '/delete_proxy':
            await AdminStates.user_delete_proxy.set()
        elif message.text == '/delete_all_proxy':
            await message.answer(
                "ТОЧНО удалить все прокси? (yes/No)", reply_markup=cancel_keyboard())
            await AdminStates.user_delete_all_proxy.set()


@logger.catch
async def add_new_proxy_handler(message: Message) -> None:
    """Обработчик введенной прокси"""

    proxies: list = re.findall(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,6}\b', message.text)
    for proxy in proxies:
        await DBI.add_new_proxy(proxy=proxy)
        await message.answer(f"Добавлена прокси: {proxy}")
    await DBI.delete_proxy_for_all_users()
    await DBI.set_new_proxy_for_all_users()


@logger.catch
async def delete_all_proxies(message: Message, state: FSMContext) -> None:
    """Удаляет все прокси."""

    if message.text.lower() == "yes":
        await DBI.delete_all_proxy()
        await ErrorsSender.send_report_to_admins(
            f"Пользователь {message.from_user.id} удалил ВСЕ прокси.")
        await state.finish()
        return
    await message.answer("Прокси не удалены.")
    await state.finish()


@logger.catch
async def delete_proxy_handler(message: Message) -> None:
    """Обработчик введенной прокси"""

    proxies: list = re.findall(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,6}\b', message.text)
    for proxy in proxies:
        await DBI.delete_proxy(proxy=proxy)
        await message.answer(f"Удалена прокси: {proxy}")


@logger.catch
async def request_user_admin_handler(message: Message) -> None:
    """Обработчик команды /add_admin"""

    if str(message.from_user.id) in admins_list:
        await message.answer(
            f'Введите telegram_id пользователя для назначения его администратором:',
            reply_markup=cancel_keyboard()
        )
        await AdminStates.name_for_admin.set()


@logger.catch
async def set_user_admin_handler(message: Message, state: FSMContext) -> None:
    """Обработчик назначения пользователя администратором """

    user_telegram_id_for_admin: str = message.text
    if await DBI.get_user_by_telegram_id(user_telegram_id_for_admin):
        await DBI.set_user_status_admin(telegram_id=user_telegram_id_for_admin)
        await message.answer(
            f'{user_telegram_id_for_admin} назначен администратором. ',
            reply_markup=user_menu_keyboard()
        )
        await bot.send_message(
            chat_id=user_telegram_id_for_admin, text='Вас назначили администратором.')
    else:
        await message.answer(f'Имя пользователя нераспознано.')
    await state.finish()


@logger.catch
async def admin_help_handler(message: Message) -> None:
    """Обработчик команды /admin"""

    user_telegram_id: str = str(message.from_user.id)
    user_is_admin: bool = await DBI.is_admin(telegram_id=user_telegram_id)
    user_is_superadmin: bool = user_telegram_id in admins_list
    if user_is_admin or user_is_superadmin:
        commands: list = [
            "\n/admin - показать список команд администратора.",
            "\n/add_user - добавить нового пользователя.",
            "\n/show_users - показать список пользователей.",
            "\n/delete_user - удалить пользователя.",
            '\n/activate_user - активировать пользователя'
        ]
        keyboard = admin_keyboard()
        if user_is_superadmin:
            superadmin: list = [
                "\n/add_admin - команда для назначения пользователя администратором",
                "\n/sendall 'тут текст сообщения без кавычек' - отправить сообщение всем активным пользователям",
                "\n/add_proxy - добавить прокси",
                "\n/delete_proxy - удалить прокси",
                "\n/delete_all_proxy - удалить ВСЕ прокси",
                "\n/set_max_tokens - изменить кол-во токенов пользователя",
                "\n/reboot - предупредить о перезагрузке, остановить работу всех ботов",
            ]
            commands.extend(superadmin)
            keyboard = superadmin_keyboard()
        admin_commands: str = "".join(commands)
        await message.answer(f'Список команд администратора: {admin_commands}')
        await message.answer(
            f'Всего отправлено символов: {Vocabulary.get_count_symbols()}',
            reply_markup=keyboard
        )
    else:
        logger.info(f'{message.from_user.id}:{message.from_user.username}: NOT AUTORIZATED')


@logger.catch
async def request_activate_user_handler(message: Message) -> None:
    """Обработчик команды /activate_user"""

    user_telegram_id: str = str(message.from_user.id)
    user_is_admin: bool = await DBI.is_admin(telegram_id=user_telegram_id)
    user_is_superadmin: bool = user_telegram_id in admins_list
    if user_is_admin or user_is_superadmin:
        users: dict = await DBI.get_all_inactive_users()
        if users:
            await message.answer("Выберите пользователя:", reply_markup=inactive_users_keyboard(users))
            await AdminStates.user_add_token.set()
        else:
            await message.answer(
                "Нет неактивных пользователей.",
                reply_markup=user_menu_keyboard()
            )


@logger.catch
async def tokens_and_hours_request_callback_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """Запрашивает количество часов и токенов для активации пользователя"""

    user_telegram_id: str = str(callback.data.rsplit("_", maxsplit=1)[-1])
    if await DBI.get_user_by_telegram_id(telegram_id=user_telegram_id):
        await callback.message.answer(
            "Введите количество часов и количество токенов для активации через пробел."
            "\nНапример: '24 10'",
            reply_markup=cancel_keyboard()
        )
        await state.update_data(activate_user=user_telegram_id)
        await AdminStates.user_activate.set()
    else:
        await callback.message.answer(
            "ОШИБКА!!!КАКИМ ТО ОБРАЗОМ ПОЛЬЗОВАТЕЛЬ НЕ НАЙДЕН",
            reply_markup=user_menu_keyboard()
        )
        await state.finish()
    await callback.answer()


@logger.catch
async def activate_user_handler(message: Message, state: FSMContext) -> None:
    """Активирует пользователя на введенное количество часов с заданным количеством токенов"""

    state_data: dict = await state.get_data()
    user_telegram_id: str = state_data.get("activate_user")

    data: list = message.text.strip().split()
    if len(data) != 2:
        await message.answer(
            "Введите количество часов и количество токенов для активации через пробел."
            "Например: '24 10'\n",
            reply_markup=cancel_keyboard()
        )
        return
    hours: int = check_is_int(data[0])
    max_tokens: int = check_is_int(data[1])
    if all((hours, max_tokens)):
        await DBI.set_max_tokens(telegram_id=user_telegram_id, max_tokens=max_tokens)
        await DBI.set_expiration_date(telegram_id=user_telegram_id, subscription_period=hours)
        await DBI.activate_user(telegram_id=user_telegram_id)
        await message.answer(
            f"Для пользователя {user_telegram_id} установлено:"
            f"\nТокенов: {max_tokens}"
            f"\nЧасов: {hours}",
            reply_markup=user_menu_keyboard()
        )
        await state.finish()
    else:
        await message.answer(
            f"Ввели неверные данные часов или количества токенов.", reply_markup=cancel_keyboard()
        )
        return


# @logger.catch
# async def max_tokens_request_handler(message: Message) -> None:
#     """Обработчик для создания нового пользователя. Команда /add_user"""
#
#     if await DBI.is_admin(telegram_id=str(message.from_user.id)):
#         if not await DBI.get_proxy_count():
#             await message.answer("Нет ни одной прокси. Добавьте хотя бы одну.", reply_markup=user_menu_keyboard())
#             return
#         await message.answer('Введите количество токенов для пользователя?', reply_markup=cancel_keyboard())
#         await AdminStates.max_tokens_req.set()
#     else:
#         logger.info(f'{message.from_user.id}:{message.from_user.username}: NOT AUTORIZATED')


# @logger.catch
# async def user_name_request_handler(message: Message, state: FSMContext) -> None:
#     """Проверка максимального количества токенов и запрос на введение имени нового пользователя"""
#
#     max_tokens: int = check_is_int(message.text)
#     if not max_tokens:
#         await message.answer(
#             'Число должно быть целым положительным. Введите еще раз.: ',
#             reply_markup=cancel_keyboard()
#         )
#         return
#     await state.update_data(max_tokens=max_tokens)
#     await message.answer('Введите имя для нового пользователя: ', reply_markup=cancel_keyboard())
#     await AdminStates.subscribe_time.set()


# @logger.catch
# async def subscribe_time_request_handler(message: Message, state: FSMContext) -> None:
#     """Проверка введеного имени и запрос времени подписки для нового пользователя"""
#
#     name: str = message.text
#     if await DBI.get_user_by_name(name=name):
#         await message.answer('Такой пользователь уже существует. '
#                              '\nВведите другое имя:')
#         return
#     if len(name) > 20:
#         await message.answer('Имя пользователя не должно превышать 20 символов. Введите заново.')
#         return
#     await state.update_data(name=name)
#     await message.answer('Введите время подписки в ЧАСАХ: ', reply_markup=cancel_keyboard())
#     await AdminStates.name_for_cr.set()


# @logger.catch
# async def add_new_user_handler(message: Message, state: FSMContext) -> None:
#     """Проверка введенного времени подписки и создание токена для нового пользователя"""
#
#     subscribe_time: int = check_is_int(message.text)
#     if message.text == "-1":
#         subscribe_time: int = -1
#     hours_in_year: int = 8760
#     if not subscribe_time or subscribe_time > hours_in_year * 2:
#         await message.answer(
#             'Время в часах должно быть целым положительным. '
#             '\nВведите еще раз время подписки в ЧАСАХ: ',
#             reply_markup=cancel_keyboard()
#         )
#         return
#     state_data: dict = await state.get_data()
#     name: str = state_data.get("name")
#     max_tokens: int = state_data.get("max_tokens", 0)
#     new_token: str = get_token(key="user")
#     tokens: dict = {
#         new_token: {
#             "name": name,
#             "max_tokens": max_tokens,
#             "subscribe_time": subscribe_time
#             }
#         }
#     add_new_token(tokens)
#     await message.answer(
#         f"Токен для нового пользователя {name}: {new_token}"
#         f"\nМаксимум токенов: {max_tokens}",
#         reply_markup=user_menu_keyboard()
#     )
#     await state.finish()


@logger.catch
async def show_all_users_handler(message: Message) -> None:
    """Обработчик команды /show_users. Показывает список всех пользователей"""

    user_telegram_id: str = str(message.from_user.id)
    user_is_admin: bool = await DBI.is_admin(telegram_id=user_telegram_id)
    user_is_superadmin: bool = user_telegram_id in admins_list
    if user_is_admin or user_is_superadmin:
        users: Tuple[namedtuple] = await DBI.get_all_users()

        lenght: int = len(users)
        for shift in range(0, lenght, 10):
            users_slice: tuple = users[shift:shift + 10]
            spam = (
                    f'{user.nick_name.rsplit("_", maxsplit=1)[0]} | '
                    f'{"Active" if user.active else "Not active"} | '
                    f'{"Admin" if user.admin else "Not admin"} | '
                    f'Proxy: {user.proxy if user.proxy else "ЧТО ТО СЛОМАЛОСЬ"} | '
                    f'\nID: {user.telegram_id if user.telegram_id else "ЧТО ТО СЛОМАЛОСЬ"} | '
                    f'№: {user.max_tokens if user.max_tokens else "ЧТО ТО СЛОМАЛОСЬ"} | '
                    f'{user.expiration if user.expiration else "ЧТО ТО СЛОМАЛОСЬ"}'
                    for user in users_slice
                )
            user_list: str = '\n'.join(spam)
            await message.answer(user_list, reply_markup=ReplyKeyboardRemove())
        await message.answer(
            f'Всего пользователей: {lenght}',
            reply_markup=ReplyKeyboardRemove()
        )
    else:
        logger.info(f'{message.from_user.id}:{message.from_user.username}: NOT AUTORIZATED')


@logger.catch
async def delete_user_name_handler(message: Message) -> None:
    """Обработчик для удаления пользователя. Команда /delete_user"""

    user_telegram_id: str = str(message.from_user.id)
    user_is_admin: bool = await DBI.is_admin(telegram_id=user_telegram_id)
    user_is_superadmin: bool = user_telegram_id in admins_list
    if user_is_admin or user_is_superadmin:
        all_users: 'Tuple[namedtuple]' = await DBI.get_all_users()
        lenght: int = len(all_users)
        for index in range(0, lenght, 10):
            keyboard = InlineKeyboardMarkup(row_width=1)
            users_group: 'Tuple[namedtuple]' = all_users[index: index + 10]
            for elem in users_group:
                text: str = f"{elem.nick_name}: {elem.telegram_id}"
                keyboard.add(InlineKeyboardButton(
                    text=text, callback_data=f'user_{elem.telegram_id}'))
            await message.answer(
                f'Выберите пользователя для удаления: {index}/{lenght}', reply_markup=keyboard)
        await message.answer("Для отмены нажмите кнопку Отмена", reply_markup=cancel_keyboard())
        await AdminStates.name_for_del.set()


@logger.catch
async def delete_user_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработчик ввода имени пользователя для удаления"""

    telegram_id: str = callback.data.rsplit("_", maxsplit=1)[-1]
    if await DBI.delete_user_by_telegram_id(telegram_id):
        message_text: str = f"Пользователь {telegram_id} удален из БД."
    else:
        message_text: str = f"Пользователь {telegram_id} не найден в БД."
    await callback.message.answer(message_text, reply_markup=user_menu_keyboard())
    await state.finish()
    await callback.answer()


# @logger.catch
# async def activate_new_user_handler(message: Message) -> None:
#     """Обработчик команды /ua для авторизации нового пользователя"""
#
#     user_telegram_id: str = str(message.from_user.id)
#     if await DBI.user_is_active(telegram_id=user_telegram_id):
#         await message.answer("Вы уже есть в базе данных.", reply_markup=cancel_keyboard())
#         return
#     await message.answer("Введите токен: ", reply_markup=cancel_keyboard())
#     await AdminStates.name_for_activate.set()


# @logger.catch
# async def final_add_user_handler(message: Message, state: FSMContext) -> None:
#     """Обработчик создания инициализации активации нового пользователя"""
#
#     user_data: dict = delete_used_token(message.text)
#     if not user_data:
#         error_text: str = (
#             "Пользователь ошибочно или повторно ввел токен."
#             "\nПри чтении токена для создания нового пользователя из файла произошла ошибка."
#             f"\nUser: {message.from_user.id}"
#             f"\nData: {message}"
#         )
#         await send_report_to_admins(error_text)
#         logger.error(error_text)
#         return
#     user_name = user_data["name"]
#     max_tokens = user_data["max_tokens"]
#     subscribe_time = user_data["subscribe_time"]
#     if user_name and max_tokens and subscribe_time:
#         user_telegram_id: str = str(message.from_user.id)
#
#         proxy_data: 'namedtuple' = await DBI.get_low_used_proxy()
#         user_data: dict = {
#             "telegram_id": user_telegram_id,
#             "nick_name": user_name,
#             "proxy_pk": proxy_data.proxy_pk,
#             "expiration": subscribe_time,
#             "max_tokens": max_tokens
#         }
#
#         if not await DBI.add_new_user(**user_data):
#             await send_report_to_admins(
#                 text=(f"При добавлении нового пользователя произошла ошибка:"
#                       f"\nПользователь {user_name} : ID: {user_telegram_id} уже существует.")
#             )
#             await message.answer('Пользователь уже существует.')
#             await state.finish()
#             return
#         await message.answer(
#             'Поздравляю, вы добавлены в БД'
#             f'\nВам назначен лимит в {max_tokens} токенов.',
#             reply_markup=user_menu_keyboard()
#         )
#         await send_report_to_admins(
#             text=f"Пользователь {user_name} : ID: {user_telegram_id} добавлен в БД."
#                  f"\nМаксимальное количество токенов: {max_tokens}"
#                  f"\nВремя подписки: {subscribe_time} часов.",
#         )
#     await state.finish()


@logger.catch
async def reboot_handler(message: Message) -> None:
    """Команда /reboot"""

    user_telegram_id: str = str(message.from_user.id)
    user_is_superadmin: bool = user_telegram_id in admins_list
    if user_is_superadmin:
        text: str = "Перезагрузка через 1 минуту. Работа бота будет остановлена автоматически."
        for user_telegram_id in await DBI.get_working_users():
            try:
                await bot.send_message(user_telegram_id, text=text)
            except aiogram.utils.exceptions.ChatNotFound:
                logger.warning(f"Chat {user_telegram_id} not found.")
            await DBI.set_user_is_not_work(str(user_telegram_id))


@logger.catch
def register_admin_handlers(dp: Dispatcher) -> None:
    """
    Регистратор для функций данного модуля
    """
    dp.register_message_handler(message_cancel_handler, commands=['отмена', 'cancel'], state="*")
    dp.register_message_handler(
        message_cancel_handler, Text(startswith=["отмена", "cancel"], ignore_case=True), state="*"
    )
    # dp.register_message_handler(
    #     final_add_user_handler, Text(startswith=["new_user_"]), state=AdminStates.name_for_activate
    # )
    dp.register_message_handler(request_user_admin_handler, commands=['add_admin'])
    dp.register_message_handler(set_user_admin_handler, state=AdminStates.name_for_admin)
    dp.register_message_handler(request_proxies_handler, commands=['add_proxy', 'delete_proxy', 'delete_all_proxy'])
    dp.register_message_handler(add_new_proxy_handler, state=AdminStates.user_add_proxy)
    dp.register_message_handler(delete_proxy_handler, state=AdminStates.user_delete_proxy)
    dp.register_message_handler(delete_all_proxies, state=AdminStates.user_delete_all_proxy)
    dp.register_message_handler(delete_user_name_handler, commands=['delete_user'])
    dp.register_callback_query_handler(delete_user_handler, Text(startswith=['user_']), state=AdminStates.name_for_del)
    dp.register_message_handler(request_activate_user_handler, commands=['activate_user'])
    dp.register_callback_query_handler(
        tokens_and_hours_request_callback_handler, Text(startswith=['activate_']), state=AdminStates.user_add_token
    )
    dp.register_message_handler(activate_user_handler, state=AdminStates.user_activate)
    dp.register_message_handler(show_all_users_handler, commands=['show_users', 'su'])
    dp.register_message_handler(reboot_handler, commands=['reboot'], state="*")
    dp.register_message_handler(admin_help_handler, commands=['admin', 'adm'])
    dp.register_message_handler(request_max_tokens_handler, commands=['set_max_tokens'])
    dp.register_message_handler(set_max_tokens_handler, state=AdminStates.user_set_max_tokens)
    dp.register_message_handler(send_message_to_all_users_handler, Text(startswith=["/sendall", "/sa"]))
