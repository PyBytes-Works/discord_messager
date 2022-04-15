"""Модуль для обработчиков администратора"""
import re

import aiogram
import aiogram.utils.exceptions
from aiogram import Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove, InlineKeyboardMarkup, \
    InlineKeyboardButton

from classes.vocabulary import Vocabulary
from config import logger, bot, admins_list
from handlers import cancel_handler
from keyboards import cancel_keyboard, user_menu_keyboard, inactive_users_keyboard
from states import UserState
from models import User, Proxy

from utils import (
    get_token, add_new_token, delete_used_token, send_report_to_admins, check_is_int
)


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
        for user in User.get_active_users():
            try:
                await bot.send_message(chat_id=user, text=data)
            except aiogram.utils.exceptions.ChatNotFound as err:
                logger.error(f"Не смог отправить сообщение пользователю {user}.", err)
            except aiogram.utils.exceptions.BotBlocked as err:
                logger.error(f"Пользователь {user} заблокировал бота", err)
                result: bool = User.deactivate_user(telegram_id=user)
                if result:
                    await send_report_to_admins(f"Пользователь {user} заблокировал бота. "
                                                f"\nЕго аккаунт деактивирован.")


@logger.catch
async def request_max_tokens_handler(message: Message) -> None:
    """Обработчик команды /set_max_tokens"""

    user_id: str = str(message.from_user.id)
    if user_id in admins_list:
        await message.answer(
            'Введите telegram_id пользователя и количество токенов через пробел. '
            '\nПример: "3333333 10"',
            reply_markup=cancel_keyboard()
        )
        await UserState.user_set_max_tokens.set()


@logger.catch
async def set_max_tokens_handler(message: Message, state: FSMContext) -> None:
    """Проверка и запись в БД нового количества токенов для пользователя"""

    telegram_id = str(message.text.strip().split()[0])
    new_tokens_count: int = check_is_int(message.text.strip().split()[-1])
    if new_tokens_count and telegram_id:
        if User.set_max_tokens(telegram_id=telegram_id, max_tokens=new_tokens_count):
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

    user_id: str = str(message.from_user.id)
    if user_id in admins_list:
        await message.answer(
            'Введите прокси в формате "123.123.123.123:5555" (можно несколько через пробел)',
            reply_markup=cancel_keyboard()
        )
        if message.text == '/add_proxy':
            await UserState.user_add_proxy.set()
        elif message.text == '/delete_proxy':
            await UserState.user_delete_proxy.set()
        elif message.text == '/delete_all_proxy':
            await message.answer("ТОЧНО удалить все прокси? (yes/No)", reply_markup=cancel_keyboard())
            await UserState.user_delete_all_proxy.set()


@logger.catch
async def add_new_proxy_handler(message: Message) -> None:
    """Обработчик введенной прокси"""

    proxies: list = re.findall(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,6}\b', message.text)
    for proxy in proxies:
        Proxy.add_proxy(proxy=proxy)
        await message.answer(f"Добавлена прокси: {proxy}")


@logger.catch
async def delete_all_proxies(message: Message, state: FSMContext) -> None:
    """Удаляет все прокси."""

    if message.text.lower() == "yes":
        Proxy.delete_all_proxy()
        await send_report_to_admins(f"Пользователь {message.from_user.id} удалил ВСЕ прокси.")
        await state.finish()
        return
    await message.answer("Прокси не удалены.")
    await state.finish()


@logger.catch
async def delete_proxy_handler(message: Message) -> None:
    """Обработчик введенной прокси"""

    proxies: list = re.findall(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,6}\b', message.text)
    for proxy in proxies:
        Proxy.delete_proxy(proxy=proxy)
        await message.answer(f"Удалена прокси: {proxy}")


@logger.catch
async def request_user_admin_handler(message: Message) -> None:
    """Обработчик команды /add_admin"""

    if str(message.from_user.id) in admins_list:
        await message.answer(f'Введите имя пользователя: ', reply_markup=cancel_keyboard())
        await UserState.name_for_admin.set()


@logger.catch
async def set_user_admin_handler(message: Message, state: FSMContext) -> None:
    """Обработчик назначения пользователя администратором """

    user_name: str = message.text
    user: 'User' = User.get_or_none(User.nick_name.contains(user_name))
    if user:
        user_id: str = str(user.telegram_id)
        User.set_user_status_admin(telegram_id=user_id)
        await message.answer(f'{user_name} назначен администратором. ', reply_markup=user_menu_keyboard())
        await bot.send_message(chat_id=user_id, text='Вас назначили администратором.')
    else:
        await message.answer(f'Имя пользователя нераспознано.')
    await state.finish()


@logger.catch
async def admin_help_handler(message: Message) -> None:
    """Обработчик команды /admin"""

    user_telegram_id: str = str(message.from_user.id)
    if User.is_admin(telegram_id=user_telegram_id):
        commands: list = [
            "\n/ua - команда для пользователя, для активации по токену.",
            "\n/admin - показать список команд администратора.",
            "\n/add_user - добавить нового пользователя.",
            "\n/show_users - показать список пользователей.",
            "\n/delete_user - удалить пользователя.",
            '\n/activate_user - активировать пользователя'
        ]
        if user_telegram_id in admins_list:
            superadmin: list = [
                "\n/add_admin - команда для назначения пользователя администратором",
                "\n/sendall 'тут текст сообщения без кавычек' - отправить сообщение всем активным пользователям",
                "\n/add_proxy - добавить прокси",
                "\n/delete_proxy - удалить прокси",
                "\n/delete_all_proxy - удалить ВСЕ прокси",
                "\n/set_max_tokens - изменить кол-во токенов пользователя",
            ]
            commands.extend(superadmin)
        admin_commands: str = "".join(commands)
        await message.answer(f'Список команд администратора: {admin_commands}')
        await message.answer(f'Всего отправлено символов: {Vocabulary.get_count_symbols()}', reply_markup=user_menu_keyboard())
    else:
        logger.info(f'{message.from_user.id}:{message.from_user.username}: NOT AUTORIZATED')


@logger.catch
async def request_activate_user_handler(message: Message) -> None:
    """Обработчик команды /activate_user"""

    user_telegram_id: str = str(message.from_user.id)
    if User.is_admin(telegram_id=user_telegram_id):
        users: dict = User.get_all_inactive_users()
        if users:
            await message.answer("Выберите пользователя:", reply_markup=inactive_users_keyboard(users))
            await UserState.user_add_token.set()
        else:
            await message.answer(
                "Нет неактивных пользователей.",
                reply_markup=user_menu_keyboard()
            )


@logger.catch
async def tokens_and_hours_request_callback_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """Запрашивает количество часов и токенов для активации пользователя"""

    user_telegram_id: str = str(callback.data.rsplit("_", maxsplit=1)[-1])
    if User.get_user_by_telegram_id(telegram_id=user_telegram_id):
        await callback.message.answer(
            "Введите количество часов и количество токенов для активации через пробел."
            "\nНапример: '24 10'",
            reply_markup=cancel_keyboard()
        )
        await state.update_data(activate_user=user_telegram_id)
        await UserState.user_activate.set()
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
    if hours and max_tokens:
        User.set_max_tokens(telegram_id=user_telegram_id, max_tokens=max_tokens)
        User.set_expiration_date(telegram_id=user_telegram_id, subscription_period=hours)
        User.activate_user(telegram_id=user_telegram_id)
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


@logger.catch
async def max_tokens_request_handler(message: Message) -> None:
    """Обработчик для создания нового пользователя. Команда /add_user"""

    if User.is_admin(telegram_id=str(message.from_user.id)):
        if not Proxy.get_proxy_count():
            await message.answer("Нет ни одной прокси. Добавьте хотя бы одну.", reply_markup=user_menu_keyboard())
            return
        await message.answer('Введите количество токенов для пользователя?', reply_markup=cancel_keyboard())
        await UserState.max_tokens_req.set()
    else:
        logger.info(f'{message.from_user.id}:{message.from_user.username}: NOT AUTORIZATED')


@logger.catch
async def user_name_request_handler(message: Message, state: FSMContext) -> None:
    """Проверка максимального количества токенов и запрос на введение имени нового пользователя"""

    max_tokens: int = check_is_int(message.text)
    if not max_tokens:
        await message.answer('Число должно быть целым положительным. Введите еще раз.: ', reply_markup=cancel_keyboard())
        return
    await state.update_data(max_tokens=max_tokens)
    await message.answer('Введите имя для нового пользователя: ', reply_markup=cancel_keyboard())
    await UserState.subscribe_time.set()


@logger.catch
async def subscribe_time_request_handler(message: Message, state: FSMContext) -> None:
    """Проверка введеного имени и запрос времени подписки для нового пользователя"""

    name: str = message.text
    user: 'User' = User.get_or_none(User.nick_name.contains(name))
    if user:
        await message.answer('Такой пользователь уже существует. Введите другое имя.')
        return
    if len(name) > 20:
        await message.answer('Имя пользователя не должно превышать 20 символов. Введите заново.')
        return
    await state.update_data(name=name)
    await message.answer('Введите время подписки в ЧАСАХ: ', reply_markup=cancel_keyboard())
    await UserState.name_for_cr.set()


@logger.catch
async def add_new_user_handler(message: Message, state: FSMContext) -> None:
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
    name: str = state_data.get("name")
    max_tokens: int = state_data.get("max_tokens", 0)
    new_token: str = get_token(key="user")
    tokens: dict = {
        new_token: {
            "name": name,
            "max_tokens": max_tokens,
            "subscribe_time": subscribe_time
            }
        }
    add_new_token(tokens)
    await message.answer(
        f"Токен для нового пользователя {name}: {new_token}"
        f"\nМаксимум токенов: {max_tokens}",
        reply_markup=user_menu_keyboard()
    )
    await state.finish()


@logger.catch
async def show_all_users_handler(message: Message) -> None:
    """Обработчик команды /show_users. Показывает список всех пользователей"""

    if User.is_admin(telegram_id=message.from_user.id):
        users: dict = User.get_all_users()
        total_values: list = list(users.values())
        lenght: int = len(total_values)
        for shift in range(0, lenght, 10):
            user_list: str = "\n".join(total_values[shift:shift + 10])
            await message.answer(user_list, reply_markup=ReplyKeyboardRemove())
        await message.answer(
            f'Список пользователей: {len(users)}',
            reply_markup=ReplyKeyboardRemove()
        )
    else:
        logger.info(f'{message.from_user.id}:{message.from_user.username}: NOT AUTORIZATED')


@logger.catch
async def delete_user_name_handler(message: Message) -> None:
    """Обработчик для удаления пользователя. Команда /delete_user"""

    if User.is_admin(telegram_id=message.from_user.id):
        all_users: dict = User.get_all_users()
        users_keys: list = list(all_users.keys())
        lenght: int = len(users_keys)
        for index in range(0, lenght, 10):
            keyboard = InlineKeyboardMarkup(row_width=1)
            slice: list = users_keys[index: index + 10]
            for telegram_id in slice:
                keyboard.add(InlineKeyboardButton(text=all_users[telegram_id], callback_data=f'user_{telegram_id}'))
            await message.answer(f'Выберите пользователя для удаления: {index}/{lenght}', reply_markup=keyboard)
        await message.answer("Для отмены нажмите кнопку Отмена", reply_markup=cancel_keyboard())
        await UserState.name_for_del.set()


@logger.catch
async def delete_user_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработчик ввода имени пользователя для удаления"""

    user_id: str = callback.data.rsplit("_", maxsplit=1)[-1]
    user: 'User' = User.get_user_by_telegram_id(telegram_id=user_id)
    name: str = user.nick_name
    if user:
        User.delete_user_by_telegram_id(user_id)
    await callback.message.answer(
        f"Пользователь {name}: {user_id} удален из БД.", reply_markup=user_menu_keyboard())
    await state.finish()
    await callback.answer()


@logger.catch
async def activate_new_user_handler(message: Message) -> None:
    """Обработчик команды /ua для авторизации нового пользователя"""
    user_telegram_id: str = str(message.from_user.id)
    if User.is_active(telegram_id=user_telegram_id):
        await message.answer("Вы уже есть в базе данных.", reply_markup=cancel_keyboard())
        return
    await message.answer("Введите токен: ", reply_markup=cancel_keyboard())
    await UserState.name_for_activate.set()


@logger.catch
async def add_user_to_db_by_token(message: Message, state: FSMContext) -> None:
    """Обработчик создания инициализации активации нового пользователя"""

    user_data: dict = delete_used_token(message.text)
    if not user_data:
        await send_report_to_admins("Пользователь ошибочно или повторно ввел токен."
                                    "\nПри чтении токена для создания нового пользователя из файла произошла ошибка."
                                    f"\nUser: {message.from_user.id}"
                                    f"\nData: {message}")
        return
    user_name = user_data["name"]
    max_tokens = user_data["max_tokens"]
    subscribe_time = user_data["subscribe_time"]
    if user_name and max_tokens and subscribe_time:
        user_telegram_id = message.from_user.id

        proxy: str = Proxy.get_low_used_proxy()
        user_created = User.add_new_user(
            telegram_id=user_telegram_id, nick_name=user_name,
            proxy=proxy, expiration=subscribe_time
        )

        if not user_created:
            await send_report_to_admins(
                text=(f"При добавлении нового пользователя произошла ошибка:"
                      f"\nПользователь {user_name} : ID: {user_telegram_id} уже существует.")
            )
            await message.answer('Пользователь уже существует.')
        else:
            tokens_set = User.set_max_tokens(telegram_id=user_telegram_id, max_tokens=max_tokens)
            if tokens_set:
                await message.answer(
                    'Поздравляю, вы добавлены в БД'
                    f'\nВам назначен лимит в {max_tokens} токенов.',
                    reply_markup=user_menu_keyboard()
                )
                await send_report_to_admins(
                    text=f"Пользователь {user_name} : ID: {user_telegram_id} добавлен в БД."
                         f"\nМаксимальное количество токенов: {max_tokens}"
                         f"\nВремя подписки: {subscribe_time} часов.",
                )
            else:
                await send_report_to_admins("Произошла ошибка при добавлении нового пользователя.")
    await state.finish()


@logger.catch
def register_admin_handlers(dp: Dispatcher) -> None:
    """
    Регистратор для функций данного модуля
    """
    dp.register_message_handler(cancel_handler, commands=['отмена', 'cancel'], state="*")
    dp.register_message_handler(
        cancel_handler, Text(startswith=["отмена", "cancel"], ignore_case=True), state="*"
    )
    dp.register_message_handler(
        add_user_to_db_by_token, Text(startswith=["new_user_"]), state=UserState.name_for_activate
    )
    dp.register_message_handler(max_tokens_request_handler, commands=['add_user', 'addu'])
    dp.register_message_handler(user_name_request_handler, state=UserState.max_tokens_req)
    dp.register_message_handler(subscribe_time_request_handler, state=UserState.subscribe_time)
    dp.register_message_handler(activate_new_user_handler, commands=['ua'])
    dp.register_message_handler(request_user_admin_handler, commands=['add_admin'])
    dp.register_message_handler(set_user_admin_handler, state=UserState.name_for_admin)
    dp.register_message_handler(request_proxies_handler, commands=['add_proxy', 'delete_proxy', 'delete_all_proxy'])
    dp.register_message_handler(add_new_proxy_handler, state=UserState.user_add_proxy)
    dp.register_message_handler(delete_proxy_handler, state=UserState.user_delete_proxy)
    dp.register_message_handler(delete_all_proxies, state=UserState.user_delete_all_proxy)
    dp.register_message_handler(delete_user_name_handler, commands=['delete_user'])
    dp.register_callback_query_handler(delete_user_handler, Text(startswith=['user_']), state=UserState.name_for_del)
    dp.register_message_handler(request_activate_user_handler, commands=['activate_user'])
    dp.register_callback_query_handler(
        tokens_and_hours_request_callback_handler, Text(startswith=['activate_']), state=UserState.user_add_token
    )
    dp.register_message_handler(activate_user_handler, state=UserState.user_activate)
    dp.register_message_handler(show_all_users_handler, commands=['show_users', 'su'])
    dp.register_message_handler(admin_help_handler, commands=['admin', 'adm'])
    dp.register_message_handler(request_max_tokens_handler, commands=['set_max_tokens'])
    dp.register_message_handler(set_max_tokens_handler, state=UserState.user_set_max_tokens)
    dp.register_message_handler(send_message_to_all_users_handler, Text(startswith=["/sendall", "/sa"]))
    dp.register_message_handler(add_new_user_handler, state=UserState.name_for_cr)
