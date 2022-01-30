"""Модуль для обработчиков администратора"""
from aiogram import Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove

from config import logger, bot, admins_list
from handlers import cancel_handler
from keyboards import cancel_keyboard, users_keyboard, user_menu_keyboard
from states import UserState
from models import User


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
#
#
from utils import get_token, add_new_token, delete_used_token, send_report_to_admins


@logger.catch
async def admin_help_handler(message: Message) -> None:
    """Обработчик команды /admin"""

    if User.is_admin(telegram_id=message.from_user.id):
        commands: tuple = (
            "\n/add_user - добавить нового пользователя",
            "\n/delete_user - удалить пользователя",
            "\n/show_users - показать список пользователей",
            "\n/admin - показать список команд администратора"
            "\n/ua - команда для пользователя, для активации по токену"
            "\n/add_admin - команда для назначения пользователя администратором"
        )
        admin_commands: str = "".join(commands)
        await message.answer(f'Список команд администратора: {admin_commands}', reply_markup=user_menu_keyboard())
    else:
        logger.info(f'{message.from_user.id}:{message.from_user.username}: NOT AUTORIZATED')
#
#
@logger.catch
async def add_new_user_name_handler(message: Message) -> None:
    """Обработчик для создания нового пользователя. Команда /add_user"""

    if User.is_admin(telegram_id=message.from_user.id):
        await message.answer('Введите имя для нового пользователя: ', reply_markup=cancel_keyboard())
        await UserState.name_for_cr.set()
    else:
        logger.info(f'{message.from_user.id}:{message.from_user.username}: NOT AUTORIZATED')
#
#
@logger.catch
async def add_new_user_handler(message: Message, state: FSMContext) -> None:
    """Обработчик ввода имени нового пользователя"""

    name: str = message.text

    user = User.get_or_none(User.nick_name.contains(name))

    if user:
        await message.answer('Такой пользователь уже существует. Введите другое имя.')
        return
    if len(name) > 20:
        await message.answer('Имя пользователя не должно превышать 20 символов. Введите заново.')
        return
    new_token: str = get_token(key="user")
    tokens: dict = {new_token: name}
    add_new_token(tokens)
    await message.answer(
        f"Токен для нового пользователя {name}: {new_token}", reply_markup=user_menu_keyboard())
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
#
#
@logger.catch
async def delete_user_name_handler(message: Message) -> None:
    """Обработчик для удаления пользователя. Команда /delete_user"""

    if User.is_admin(telegram_id=message.from_user.id):
        await message.answer('Выберите пользователя для удаления: ', reply_markup=users_keyboard())
        await message.answer("Для отмены нажмите кнопку Отмена", reply_markup=cancel_keyboard())
        await UserState.name_for_del.set()
    else:
        logger.info(f'{message.from_user.id}:{message.from_user.username}: NOT AUTORIZATED')
#
#
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
#
#
@logger.catch
async def activate_new_user_handler(message: Message) -> None:
    """Обработчик команды /ua для авторизации нового пользователя"""

    await message.answer("Введите токен: ", reply_markup=cancel_keyboard())
    await UserState.name_for_activate.set()
#
#
@logger.catch
async def add_user_to_db_by_token(message: Message, state: FSMContext) -> None:
    """Обработчик создания инициализации активации нового пользователя"""

    user: str = delete_used_token(message.text)
    if user:
        user_id = message.from_user.id
        if not User.add_new_user(telegram_id=user_id, nick_name=user):
            await send_report_to_admins(
                text=f"Пользователь {user} : ID: {user_id} уже существует."
            )
        else:
            await message.answer(
                'Поздравляю, вы добавлены в БД рассылки. '
                'Введите команду /lots или отправьте любое сообщение для вызова помощи.',
                reply_markup=user_menu_keyboard()
            )
            await send_report_to_admins(
                text=f"Пользователь {user} : ID: {user_id} добавлен в БД.",
            )
    await state.finish()


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
    dp.register_message_handler(add_new_user_name_handler, commands=['add_user'])
    dp.register_message_handler(
        activate_new_user_handler, commands=['ua'])
    dp.register_message_handler(admin_help_handler, commands=['admin'])
    dp.register_message_handler(request_user_admin_handler, commands=['add_admin'])
    dp.register_message_handler(set_user_admin_handler, state=UserState.name_for_admin)
    dp.register_message_handler(show_all_users_handler, commands=['show_users'])
    dp.register_message_handler(delete_user_name_handler, commands=['delete_user'])
    dp.register_callback_query_handler(delete_user_handler, Text(startswith=['user_']), state=UserState.name_for_del)
    dp.register_message_handler(add_new_user_handler, state=UserState.name_for_cr)
