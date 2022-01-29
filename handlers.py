"""Модуль с основными обработчиками команд, сообщений и коллбэков"""
import re
from aiogram.dispatcher.filters import Text
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.dispatcher import FSMContext

from config import logger, Dispatcher, users_data_storage
from models import User, UserTokenDiscord
from keyboards import cancel_keyboard, user_menu_keyboard
from discord_handler import MessageReceiver, DataStore, MessageSender
from states import UserState
from utils import str_to_int


@logger.catch
async def cancel_handler(message: Message, state: FSMContext) -> None:
    """
    Отменяет текущие запросы и сбрасывает состояние.
    Ставит пользователя в нерабочее состояние.
    """
    user = message.from_user.id
    logger.info(f'CANCELED')
    await state.finish()
    await message.answer("Ввод отменен.")
    User.set_user_is_not_work(user)


@logger.catch
async def invitation_add_discord_token_handler(message: Message) -> None:
    """Запрос discord-токена """
    user = message.from_user.id
    if User.is_active(telegram_id=user):
        if UserTokenDiscord.get_number_of_free_slots_for_tokens(user):
            await message.answer("Введите discord-токен", reply_markup=cancel_keyboard())
            await UserState.user_add_token.set()
            return
        await message.answer(
            "Максимальное количество discord-токенов уже добавлено", reply_markup=user_menu_keyboard())


@logger.catch
async def add_discord_token_handler(message: Message, state: FSMContext) -> None:
    """ Получение токена запрос ссылки на канал"""

    token = message.text
    await state.update_data(token=token)
    await message.answer(
        "Введите ссылку на канал (должна заканчиваться на 2 числа через /)",
        reply_markup=cancel_keyboard()
    )
    await UserState.user_add_channel.set()


@logger.catch
async def add_channel_handler(message: Message, state: FSMContext) -> None:
    """
        получения ссылки на канал, запрос прокси
    """
    mess = message.text
    guild, channel = mess.rsplit('/', maxsplit=3)[-2:]
    guild = str_to_int(guild)
    channel = str_to_int(channel)
    if not guild or not channel:
        await message.answer(
            "Проверьте ссылку на канал и попробуйте ещё раз", reply_markup=cancel_keyboard())
        return

    await state.update_data(guild=guild, channel=channel)
    await message.answer(
        "Введите ip прокси (ip адрес:порт )", reply_markup=cancel_keyboard())
    await UserState.user_add_proxy.set()


@logger.catch
async def add_proxy_handler(message: Message, state: FSMContext) -> None:
    """
        добавить прокси
    """

    proxy = message.text
    proxy = re.match(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,6}\b', proxy.strip())

    if not proxy:
        await message.answer(
            "Проверьте proxy и попробуйте ещё раз", reply_markup=cancel_keyboard())
        return

    await state.update_data(proxy=proxy.string)
    await message.answer(
        "Добавьте language ru, es, en или другой)", reply_markup=cancel_keyboard())
    await UserState.user_add_language.set()


@logger.catch
async def add_language_handler(message: Message, state: FSMContext) -> None:
    """
       проверка и запись, либо возврат в другое состояние
    """


    await UserState.user_add_proxy.set()
    pass
##################


@logger.catch
async def start_command_handler(message: Message) -> None:
    """Получает случайное сообщение из дискорда, ставит машину состояний в положение
    'жду ответа пользователя'
    """

    await message.answer("Начинаю получение данных", reply_markup=cancel_keyboard())
    print("Создаю экземпляр класса-хранилища")
    new_store = DataStore(message.from_user.id)
    print("Добавляю его в общее хранилище")
    users_data_storage.add_instance(telegram_id=message.from_user.id, data=new_store)
    print("Отправляю запрос к АПИ")
    text = MessageReceiver.get_message(new_store)
    print("Получаю ответ", text)
    await message.answer(f"Данные получены:"
                         f"\nСообщение: {text}")
    await UserState.user_wait_message.set()


@logger.catch
async def send_to_discord(message: Message, state: FSMContext) -> None:
    """Отправляет полученное сообщение в дискорд"""

    text = message.text
    if len(text) > 50:
        await message.answer(
            "Сообщение не должно быть длиннее 50 символов. Попробуй еще раз.",
            reply_markup=cancel_keyboard()
        )
        return
    await message.answer("Понял, принял, отправляю.", reply_markup=cancel_keyboard())
    datastore = users_data_storage.get_instance(message.from_user.id)
    result = MessageSender.send_message(text=message.text, datastore=datastore)
    await message.answer(f"Результат отправки: {result}", reply_markup=ReplyKeyboardRemove())
    await state.finish()


@logger.catch
async def default_message(message: Message) -> None:
    """Ответ на любое необработанное действие активного пользователя."""

    if User.is_active(message.from_user.id):
        await message.answer(
            'Доступные команды\n'
            '/start - Активирует бота.'
        )


@logger.catch
def register_handlers(dp: Dispatcher) -> None:
    """
    Регистратор для функций данного модуля
    """
    dp.register_message_handler(
        cancel_handler, commands=['отмена', 'cancel'], state="*")
    dp.register_message_handler(
        cancel_handler, Text(startswith=["отмена", "cancel"], ignore_case=True), state="*")
    dp.register_message_handler(start_command_handler, commands=["start", "старт"])
    dp.register_message_handler(invitation_add_discord_token_handler, commands=["at", "addtoken", "add_token"])
    dp.register_message_handler(add_discord_token_handler, state=UserState.user_add_token)
    dp.register_message_handler(send_to_discord, state=UserState.user_wait_message)
    dp.register_message_handler(add_discord_token_handler, state=UserState.user_add_token)
    dp.register_message_handler(add_channel_handler, state=UserState.user_add_channel)
    dp.register_message_handler(add_proxy_handler, state=UserState.user_add_proxy)
    dp.register_message_handler(add_language_handler, state=UserState.user_add_language)
    dp.register_message_handler(default_message)
