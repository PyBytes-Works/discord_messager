"""Модуль для обработчиков администратора"""
from aiogram import Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove

from config import logger, bot, admins_list, DEFAULT_PROXY
from handlers import cancel_handler
from keyboards import cancel_keyboard, users_keyboard, user_menu_keyboard
from states import UserState
from models import User

from utils import (
    get_token, add_new_token, delete_used_token, send_report_to_admins, check_is_int,
    get_random_proxy
)


@logger.catch
async def send_message_to_all_users_handler(message: Message) -> None:
    """Обработчик команды /sendall"""

    data = message.text[9:]
    user_id = str(message.from_user.id)
    if not data:
        await message.answer("Нет данных для отправки.")
        return
    if user_id in admins_list:
        for user in User.get_active_users():
            await bot.send_message(chat_id=user, text=data)


@logger.catch
async def request_user_admin_handler(message: Message) -> None:
    """Обработчик команды /add_admin"""

    user_id = str(message.from_user.id)
    if User.is_admin(user_id) and user_id in admins_list:
        await message.answer(f'Введите имя пользователя: ', reply_markup=cancel_keyboard())
        await UserState.name_for_admin.set()
    else:
        logger.info(f'{message.from_user.id}:{message.from_user.username}: NOT AUTORIZATED')


@logger.catch
async def set_user_admin_handler(message: Message, state: FSMContext) -> None:
    """Обработчик назначения пользователя администратором """

    user_name = message.text
    user = User.get_or_none(User.nick_name.contains(user_name))
    if user:
        user_id = user.telegram_id
        User.set_user_status_admin(telegram_id=user_id)
        await message.answer(f'{user_name} назначен администратором. ', reply_markup=user_menu_keyboard())
        await bot.send_message(chat_id=user_id, text='Вас назначили администратором.')
    else:
        await message.answer(f'Имя пользователя нераспознано.')
    await state.finish()


@logger.catch
async def admin_help_handler(message: Message) -> None:
    """Обработчик команды /admin"""

    if User.is_admin(telegram_id=message.from_user.id):
        commands: tuple = (
            "\n/admin - показать список команд администратора",
            "\n/add_user - добавить нового пользователя",
            "\n/show_users - показать список пользователей",
            "\n/ua - команда для пользователя, для активации по токену",
            "\n/add_admin - команда для назначения пользователя администратором",
            "\n/delete_user - удалить пользователя",
            "\n/sendall 'тут текст сообщения без кавычек' - отправить сообщение всем активным пользователям",
        )
        admin_commands: str = "".join(commands)
        await message.answer(f'Список команд администратора: {admin_commands}', reply_markup=user_menu_keyboard())
    else:
        logger.info(f'{message.from_user.id}:{message.from_user.username}: NOT AUTORIZATED')


@logger.catch
async def max_user_request_handler(message: Message) -> None:
    """Обработчик для создания нового пользователя. Команда /add_user"""

    if User.is_admin(telegram_id=message.from_user.id):
        await message.answer('Сколько максимум токенов будет у пользователя?', reply_markup=cancel_keyboard())
        await UserState.max_tokens_req.set()
    else:
        logger.info(f'{message.from_user.id}:{message.from_user.username}: NOT AUTORIZATED')


@logger.catch
async def add_new_user_name_handler(message: Message, state: FSMContext) -> None:
    """Проверка максимального количества токенов и запрос на введение имени нового пользователя"""

    max_tokens = check_is_int(message.text)
    if max_tokens is None or max_tokens % 2:
        await message.answer('Число должно быть четным целым положительным. Введите еще раз.: ', reply_markup=cancel_keyboard())
        return
    await state.update_data(max_tokens=max_tokens)
    await message.answer('Введите имя для нового пользователя: ', reply_markup=cancel_keyboard())
    await UserState.subscribe_time.set()


@logger.catch
async def add_subscribe_time_handler(message: Message, state: FSMContext) -> None:
    """Проверка введеного имени и запрос времени подписки для нового пользователя"""

    name: str = message.text
    user = User.get_or_none(User.nick_name.contains(name))
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

    subscribe_time = check_is_int(message.text)
    hours_in_year = 8760
    if not subscribe_time or subscribe_time > hours_in_year * 2:
        await message.answer(
            'Время в часах должно быть четным целым положительным. '
            '\nВведите еще раз время подписки в ЧАСАХ: ',
            reply_markup=cancel_keyboard()
        )
        return
    state_data = await state.get_data()
    name = state_data.get("name")
    max_tokens = state_data.get("max_tokens", 0)
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
        user_list: str = "\n".join(tuple(users.values()))
        await message.answer(
            f'Список пользователей: {len(users)}',
            reply_markup=ReplyKeyboardRemove()
        )

        await message.answer(user_list, reply_markup=ReplyKeyboardRemove())
    else:
        logger.info(f'{message.from_user.id}:{message.from_user.username}: NOT AUTORIZATED')


@logger.catch
async def delete_user_name_handler(message: Message) -> None:
    """Обработчик для удаления пользователя. Команда /delete_user"""

    if User.is_admin(telegram_id=message.from_user.id):
        await message.answer('Выберите пользователя для удаления: ', reply_markup=users_keyboard())
        await message.answer("Для отмены нажмите кнопку Отмена", reply_markup=cancel_keyboard())
        await UserState.name_for_del.set()
    else:
        logger.info(f'{message.from_user.id}:{message.from_user.username}: NOT AUTORIZATED')


@logger.catch
async def delete_user_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработчик ввода имени пользователя для удаления"""

    user_id: str = callback.data.rsplit("_", maxsplit=1)[-1]
    user: 'User' = User.get_user_by_telegram_id(telegram_id=user_id)
    name: str = user.nick_name
    print(user_id, name)
    if user:
        User.delete_user_by_telegram_id(user_id)
    await callback.message.answer(
        f"Пользователь {name}: {user_id} удален из БД.", reply_markup=user_menu_keyboard())
    await state.finish()
    await callback.answer()


@logger.catch
async def activate_new_user_handler(message: Message) -> None:
    """Обработчик команды /ua для авторизации нового пользователя"""
    user_telegram_id = message.from_user.id
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
                                    "\r\nПри чтении токена для создания нового пользователя из файла произошла ошибка."
                                    f"\r\nUser: {message.from_user.id}"
                                    f"\r\nData: {message}")
        return
    user_name = user_data["name"]
    max_tokens = user_data["max_tokens"]
    subscribe_time = user_data["subscribe_time"]
    if user_name and max_tokens and subscribe_time:
        user_telegram_id = message.from_user.id

        # НЕ УДАЛЯТЬ, РАССКОМЕНТИРОВАТЬ КОГДА БУДУТ ПРОКСИ И ДОПИСАТЬ ФУНКЦИЮ!!!!
        # try:
        #     proxy = get_random_proxy()
        # except IndexError as err:
        #     text = f"Get random proxy error: {err}"
        #     logger.error(text)
        #     message = f"Свободные прокси закончились, не могу зарегистрировать пользователя {user_name}."
        #     await send_report_to_admins(text=message + text)
        #     await state.finish()
        proxy = DEFAULT_PROXY
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
                         f"\r\nМаксимальное количество токенов: {max_tokens}"
                         f"\r\nВремя подписки: {subscribe_time}",
                )
            else:
                await send_report_to_admins("Произошла ошибка при добавлении нового пользователя.")
    await state.finish()


@logger.catch
async def set_user_max_tokens_handler(message: Message) -> None:
    """Обработчик команды /set_max_tokens"""
    # TODO написать !!!
    user_telegram_id = message.from_user.id
    if user_telegram_id in admins_list:
        users: dict = User.get_all_users()
        user_list: str = "\n".join(tuple(users.values()))
        await message.answer(
            f'Список пользователей: {len(users)}',
            reply_markup=ReplyKeyboardRemove()
        )
        await message.answer(user_list, reply_markup=ReplyKeyboardRemove())


@logger.catch
def register_admin_handlers(dp: Dispatcher) -> None:
    """
    Регистратор для функций данного модуля
    """
    dp.register_message_handler(cancel_handler, commands=['отмена', 'cancel'], state="*")
    dp.register_message_handler(
        cancel_handler, Text(startswith=["отмена", "cancel"], ignore_case=True), state="*")
    dp.register_message_handler(
        add_user_to_db_by_token, Text(startswith=["new_user_"]), state=UserState.name_for_activate)
    dp.register_message_handler(send_message_to_all_users_handler, Text(startswith=["/sendall"]))
    dp.register_message_handler(max_user_request_handler, commands=['add_user'])
    dp.register_message_handler(add_new_user_name_handler, state=UserState.max_tokens_req)
    dp.register_message_handler(add_subscribe_time_handler, state=UserState.subscribe_time)
    dp.register_message_handler(
        activate_new_user_handler, commands=['ua'])
    dp.register_message_handler(admin_help_handler, commands=['admin'])
    dp.register_message_handler(request_user_admin_handler, commands=['add_admin'])
    dp.register_message_handler(set_user_admin_handler, state=UserState.name_for_admin)
    dp.register_message_handler(show_all_users_handler, commands=['show_users'])
    dp.register_message_handler(delete_user_name_handler, commands=['delete_user'])
    dp.register_message_handler(set_user_max_tokens_handler, commands=['set_max_tokens'])
    dp.register_callback_query_handler(delete_user_handler, Text(startswith=['user_']), state=UserState.name_for_del)
    dp.register_message_handler(add_new_user_handler, state=UserState.name_for_cr)
