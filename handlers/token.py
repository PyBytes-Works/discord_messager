from collections import namedtuple
from typing import List

import aiogram
from aiogram.dispatcher.filters import Text
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.dispatcher import FSMContext
import aiogram.utils.exceptions

from classes.request_classes import GetMe, ProxyChecker, TokenChecker
from handlers import cancel_handler
from states import TokenStates, UserChannelStates
from utils import check_is_int
from classes.db_interface import DBI
from classes.errors_reporter import ErrorsReporter
from config import logger, Dispatcher, bot
from keyboards import (
    user_menu_keyboard, cancel_keyboard, new_channel_key, yes_no_buttons, channel_menu_keyboard,
    CHANNEL_MENU
)


@logger.catch
async def select_channel_handler(message: Message) -> None:
    """
    Select channel for next commands:
    Commands: 'Установить кулдаун', Добавить токен
    :param message:
    :return:
    """

    if await DBI.is_expired_user_deactivated(message):
        return
    telegram_id: str = str(message.from_user.id)
    channels: List[namedtuple] = await DBI.get_user_channels(telegram_id=telegram_id)
    if not channels:
        await message.answer(
            "У вас нет ни одного канала. Сначала нужно создать новый канал и добавить в него токен",
            reply_markup=new_channel_key()
        )
        await TokenStates.create_channel.set()
        return
    if message.text == CHANNEL_MENU.cooldown:
        for elem in channels:
            keyboard = InlineKeyboardMarkup(row_width=1)
            keyboard.add(InlineKeyboardButton(
                text="Выбрать",
                callback_data=f"{elem.user_channel_pk}")
            )
            text: str = f"Имя канала: {elem.channel_name}\nСервер/канал: {elem.guild_id}/{elem.channel_id}"
            await message.answer(text, reply_markup=keyboard)
            await message.answer("Для какого канала установить кулдаун?", reply_markup=cancel_keyboard())
            await TokenStates.add_channel_cooldown.set()
    elif message.text == "Добавить токен":
        for elem in channels:
            keyboard = InlineKeyboardMarkup(row_width=1)
            keyboard.add(InlineKeyboardButton(
                text="Добавить сюда",
                callback_data=f"{elem.user_channel_pk}")
            )
            text: str = f"Имя канала: {elem.channel_name}\nСервер/канал: {elem.guild_id}/{elem.channel_id}"
            await message.answer(text, reply_markup=keyboard)
        await message.answer("В какой канал добавить токен?", reply_markup=new_channel_key())
        await TokenStates.select_channel.set()


@logger.catch
async def ask_token_for_selected_channel_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Ask token for check and add to selected channel
    :param callback:
    :param state:
    :return:
    """
    await state.update_data(user_channel_pk=callback.data)
    link: str = "https://teletype.in/@ted_crypto/Txzfz8Vuwd2"
    await callback.message.answer(
        "\nЧтобы узнать свой токен - перейдите по ссылке: "
        f"\n{link}"
    )
    await callback.message.answer("Введите токен:", reply_markup=cancel_keyboard())
    await TokenStates.check_token.set()
    await callback.answer()


@logger.catch
async def start_create_channel_handler(callback: CallbackQuery) -> None:
    """
    Asks link for guild/channel
    :param callback:
    :return:
    """

    await callback.message.answer(
        "Введите ссылку на канал в виде: "
        "https://discord.com/channels/932034587264167975/932034858906401842",
        reply_markup=cancel_keyboard()
    )
    await TokenStates.add_token.set()
    await callback.answer()


@logger.catch
async def check_channel_and_add_token_handler(message: Message, state: FSMContext) -> None:
    """
    Checks link for guild/channel and asks token
    :param message:
    :param state:
    :return:
    """

    try:
        guild, channel = message.text.rsplit('/', maxsplit=3)[-2:]
    except ValueError as err:
        logger.error(f"ValueError: {err}")
        guild: str = ''
        channel: str = ''
    guild: int = check_is_int(guild)
    channel: int = check_is_int(channel)
    if not all((guild, channel)):
        await message.answer(
            "Проверьте ссылку на канал и попробуйте ещё раз", reply_markup=cancel_keyboard())
        return

    await state.update_data(guild=guild, channel=channel)
    link: str = "https://teletype.in/@ted_crypto/Txzfz8Vuwd2"
    await message.answer(
        "\nЧтобы узнать свой токен - перейдите по ссылке: "
        f"\n{link}"
    )
    await message.answer("Введите токен:", reply_markup=cancel_keyboard())
    await TokenStates.check_token.set()


@logger.catch
async def check_and_add_token_handler(message: Message, state: FSMContext) -> None:
    """
    Get proxy for current user, get discord_id by token, adds user_channel and adds token
    to user_channel
    :param message:
    :param state:
    :return:
    """

    telegram_id: str = str(message.from_user.id)
    await message.answer("Проверяю данные...")
    token: str = message.text.strip()
    if await DBI.is_token_exists(token):
        await message.answer(
            "Такой токен токен уже есть в база данных."
            "\nПовторите ввод токена.",
            reply_markup=cancel_keyboard()
        )
        return

    data: dict = await state.get_data()
    channel: int = data.get('channel')
    guild: int = data.get('guild')
    user_channel_pk: int = int(data.get("user_channel_pk", 0))
    if user_channel_pk:
        channel_data: namedtuple = await DBI.get_channel(user_channel_pk=user_channel_pk)
        if channel_data:
            channel: int = channel_data.channel_id

    proxy: str = await ProxyChecker().get_checked_proxy(telegram_id=telegram_id)
    if proxy == 'no proxies':
        await message.answer(
            "Ошибка прокси. Нет доступных прокси.",
            reply_markup=user_menu_keyboard())
        await ErrorsReporter.send_report_to_admins("Нет доступных прокси.")
        await state.finish()
        return
    discord_id: str = await GetMe().get_discord_id(token=token, proxy=proxy)
    await message.answer("Получаю дискорд id.")
    if not discord_id:
        error_text: str = (f"Не смог определить discord_id для токена:"
                           f"\nToken: [{token}]"
                           f"\nGuild/channel: [{guild}: {channel}]")
        await message.answer(error_text, reply_markup=user_menu_keyboard())
        await state.finish()
        return
    if await DBI.check_token_by_discord_id(discord_id=discord_id):
        error_text: str = 'Токен с таким дискорд id уже сущестует в базе'
        await message.answer(error_text, reply_markup=user_menu_keyboard())
        await state.finish()
        return
    await message.answer(f"Дискорд id получен: {discord_id}"
                         f"\nПроверяю токен.")

    if not await TokenChecker().check_token(
            token=token, proxy=proxy, channel=channel, telegram_id=telegram_id):
        await state.finish()
        return
    await message.answer("Токен прошел проверку.")
    if user_channel_pk == 0:
        user_channel_pk: int = await DBI.add_user_channel(
            telegram_id=telegram_id, channel_id=channel, guild_id=guild)
        await message.answer(f"Создаю канал {channel}")
        if not user_channel_pk:
            await message.answer(
                text=f"Не смог добавить канал:\n{telegram_id}:{channel}:{guild}",
                reply_markup=user_menu_keyboard()
            )
            await state.finish()
            return
    await message.answer(f"Канал {channel} создан."
                         f"\nДобавляю токен в канал...")

    if not await DBI.add_token_by_telegram_id(
            telegram_id=telegram_id, token=token, discord_id=discord_id,
            user_channel_pk=user_channel_pk
    ):
        error_text: str = (f"Не добавить токен:"
                           f"\nToken: [{token}]"
                           f"\nChannel: {channel}]")
        await message.answer(error_text, reply_markup=user_menu_keyboard())
        await state.finish()
        return
    await message.answer(
        "Токен удачно добавлен."
        "\nХотите ввести кулдаун для данного канала?",
        reply_markup=yes_no_buttons(yes_msg=f'set_cooldown_{user_channel_pk}', no_msg='endof')
    )
    await state.finish()


@logger.catch
async def ask_channel_cooldown_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Asks cooldown for user_channel
    :param callback:
    :param state:
    :return:
    """
    try:
        user_channel_pk: int = check_is_int(callback.data.rsplit("_", maxsplit=1)[-1])
        await state.update_data(user_channel_pk=user_channel_pk)
        await callback.message.answer("Введите время кулдауна в минутах:", reply_markup=cancel_keyboard())
        await TokenStates.add_channel_cooldown.set()
        await callback.answer()
    except aiogram.utils.exceptions.InvalidQueryID:
        logger.warning("Сообщение просрочено.")
        await state.finish()


@logger.catch
async def add_channel_cooldown_handler(message: Message, state: FSMContext) -> None:
    """
    Checks and update cooldown for user_channel
    :param message:
    :param state:
    :return:
    """
    cooldown: int = check_is_int(message.text)
    if not cooldown:
        await message.answer(
            "Попробуйте ещё раз. Cooldown должен быть целым положительным числом: ",
            reply_markup=cancel_keyboard())
        return
    cooldown *= 60
    data = await state.get_data()
    channel_data: str = data.get("user_channel_pk")
    if not channel_data:
        await message.answer("Ошибка выбора канала.", reply_markup=user_menu_keyboard())
        await state.finish()
        return
    user_channel_pk: int = int(channel_data)
    if not await DBI.update_user_channel_cooldown(user_channel_pk=user_channel_pk, cooldown=cooldown):
        error_text: str = (f"Не смог установить кулдаун для канала:"
                           f"\nuser_channel_pk: [{user_channel_pk}: cooldown: {cooldown}]")
        await message.answer(text=error_text, reply_markup=user_menu_keyboard())
        await state.finish()
        return
    await message.answer("Кулдаун установлен.", reply_markup=user_menu_keyboard())
    logger.info(f"User: {message.from_user.id} set cooldown {cooldown} for channel {user_channel_pk}")
    await state.finish()


@logger.catch
async def info_tokens_handler(message: Message) -> None:
    """
    Выводит инфо о токенах. Обработчик кнопки "Информация"
    """

    if await DBI.is_expired_user_deactivated(message):
        return
    telegram_id: str = str(message.from_user.id)
    all_tokens: List[namedtuple] = await DBI.get_all_tokens_info(telegram_id)
    for token_info in all_tokens:
        mess: str = (
            f"Имя токена: {token_info.token_name}"
            f"\nТокен: {token_info.token}"
            f"\nКанал: {token_info.channel_id}"
            f"\nДискорд id: {token_info.token_discord_id}"
            f"\nДискорд id напарника: {token_info.mate_discord_id}"
            f"\nКуллдаун канала: {token_info.cooldown} сек."
        )
        keyboard: 'InlineKeyboardMarkup' = InlineKeyboardMarkup(row_width=2)
        keyboard.add(InlineKeyboardButton(
            text="Удалить токен.", callback_data=f"del_token_{token_info.token_pk}"),
            InlineKeyboardButton(
                text="Переименовать токен.", callback_data=f"rename_token_{token_info.token_pk}"))
        await message.answer(mess, reply_markup=keyboard)

    date_expiration: int = await DBI.get_expiration_date(telegram_id)
    if not all_tokens:
        await message.answer(
            f'Подписка истекает  {date_expiration}'
            f'\nНет ни одного токена в данном канале.', reply_markup=user_menu_keyboard())
        return

    free_slots: int = await DBI.get_number_of_free_slots_for_tokens(telegram_id)
    count_tokens: int = len(all_tokens)
    await message.answer(
        f'Подписка истекает:  {date_expiration}'
        f'\nВсего токенов: {count_tokens}'
        f'\nСвободно слотов: {free_slots}',
        reply_markup=user_menu_keyboard()
    )


@logger.catch
async def delete_token_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """Хэндлер для нажатия на кнопку "Удалить токен" """

    telegram_id: str = str(callback.from_user.id)
    if await DBI.is_user_work(telegram_id=telegram_id):
        await callback.message.answer("Бот запущен, сначала остановите бота.", reply_markup=cancel_keyboard())
        return
    token_pk: int = int(callback.data.rsplit('_', maxsplit=1)[-1])
    await DBI.delete_token_by_pk(token_pk=token_pk)
    await callback.message.answer("Токен удален.", reply_markup=user_menu_keyboard())
    try:
        await callback.message.delete()
    except aiogram.utils.exceptions.MessageToDeleteNotFound as err:
        logger.error(f"MessageToDeleteNotFound: {err}")
    await state.finish()
    await callback.answer()


@logger.catch
async def no_cooldown_enter_handler(callback: CallbackQuery) -> None:
    """Хэндлер для нажатия на кнопку "Нет" при выборе "Установить кулдаун или нет """

    await callback.message.answer("Установлен кулдаун по умолчанию: 1 минута.", reply_markup=user_menu_keyboard())
    await callback.answer()


@logger.catch
async def rename_token_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """Хэндлер для нажатия на кнопку "Переименовать токен" """

    token_pk: int = int(callback.data.rsplit('_', maxsplit=1)[-1])
    await state.set_state(TokenStates.set_name_for_token)
    await state.update_data({'token_pk': token_pk})
    await callback.message.answer("Введите новое имя.", reply_markup=cancel_keyboard())
    await callback.message.delete()


@logger.catch
async def menu_channel_handler(message: Message) -> None:
    """
    вывести меню каналов:
    text: 'Каналы'
    """

    if await DBI.is_expired_user_deactivated(message):
        return
    await message.answer('Выберите действие:', reply_markup=channel_menu_keyboard())
    await message.delete()


@logger.catch
async def list_channel_handler(message: Message, state: FSMContext) -> None:
    """
    Вывести список каналов для переименования:
    """
    if await DBI.is_expired_user_deactivated(message):
        return
    telegram_id: str = str(message.from_user.id)
    channels: List[namedtuple] = await DBI.get_user_channels(telegram_id=telegram_id)
    if not channels:
        await message.answer(
            "У вас нет ни одного канала. Сначала нужно создать новый канал и добавить в него токен",
            reply_markup=user_menu_keyboard()
        )
        await message.delete()
        await state.finish()
        return
    await state.set_state(UserChannelStates.select_user_channel_to_rename)
    # await state.update_data({'start_message': message.message_id})
    list_messages = [message.message_id]
    for elem in channels:
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(InlineKeyboardButton(
            text="Переименовать канал",
            callback_data=f"{elem.user_channel_pk}")
        )
        text: str = f"Имя канала: {elem.channel_name}\nСервер/канал: {elem.guild_id}/{elem.channel_id}"
        mess = await message.answer(text, reply_markup=keyboard)
        list_messages.append(mess.message_id)
    await message.delete()
    mess = await message.answer('Выберите действие', reply_markup=cancel_keyboard())
    list_messages.append(mess.message_id)
    await state.update_data({'messages': list_messages})


@logger.catch
async def rename_channel_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """Хэндлер для нажатия на кнопку "Переименовать канал" """
    user_channel_pk: int = int(callback.data)

    await state.set_state(UserChannelStates.enter_name_for_user_channel)
    await state.update_data({'user_channel_pk': user_channel_pk})
    mess = await callback.message.answer("Введите новое имя.", reply_markup=cancel_keyboard())
    data: dict = await state.get_data()
    old_messages = data.get('messages', [])
    old_messages.append(mess.message_id)
    await state.update_data({'messages': old_messages})


@logger.catch
async def set_user_channel_name(message: Message, state: FSMContext) -> None:
    """Хэндлер для переименования канала """

    if await DBI.is_expired_user_deactivated(message):
        return
    name = message.text
    data: dict = await state.get_data()
    user_channel_pk: int = data.get('user_channel_pk')
    old_messages = data.get('messages', [])
    chat_id = message.chat.id
    await message.delete()

    for message_id in old_messages:
        try:
            await bot.delete_message(message.chat.id, message_id=message_id)
        except aiogram.utils.exceptions.MessageToDeleteNotFound as err:
            logger.error(f"MessageToDeleteNotFound: {err}")

    await DBI.set_user_channel_name(user_channel_pk=user_channel_pk, name=name)
    await state.finish()
    await bot.send_message(chat_id, "Канал переименован.", reply_markup=user_menu_keyboard())


# TODO переписать дублирование кода
@logger.catch
async def list_channel_handler_for_delete(message: Message, state: FSMContext) -> None:
    """
    вывести список каналов для удаления:
    :param message:
    :return:
    """
    if await DBI.is_expired_user_deactivated(message):
        return
    telegram_id: str = str(message.from_user.id)
    channels: List[namedtuple] = await DBI.get_user_channels(telegram_id=telegram_id)
    if not channels:
        await message.answer(
            "У вас нет ни одного канала. Сначала нужно создать новый канал и добавить в него токен.",
            reply_markup=cancel_keyboard()
        )
        return

    await state.set_state(UserChannelStates.checks_tokens_for_user_channel)

    list_messages = []

    for elem in channels:
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(InlineKeyboardButton(
            text="Удалить канал",
            callback_data=f"{elem.user_channel_pk}")
        )
        text: str = f"Имя канала: {elem.channel_name}\nСервер/канал: {elem.guild_id}/{elem.channel_id}"
        mess = await message.answer(text, reply_markup=keyboard)
        list_messages.append(mess.message_id)
    mess = await message.answer('Выберите действие', reply_markup=cancel_keyboard())
    list_messages.append(mess.message_id)
    await state.update_data({'messages': list_messages})


@logger.catch
async def check_tokens_for_user_channel_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """Хэндлер для нажатия на кнопку "Удалить канал" """

    await state.set_state(UserChannelStates.delete_for_user_channel)
    user_channel_pk: int = int(callback.data)

    await state.update_data({'user_channel_pk': user_channel_pk})
    data: dict = await state.get_data()
    old_messages = data.get('messages', [])
    old_messages.append(callback.message.message_id)
    if await DBI.get_count_tokens_by_user_channel(user_channel_pk=user_channel_pk):
        keyboard = InlineKeyboardMarkup(row_width=3)
        keyboard.add(InlineKeyboardButton(
            text="Удалить канал",
            callback_data=f"{'True'}"))
        keyboard.add(InlineKeyboardButton(
            text="Отмена",
            callback_data=f"{'False'}"))
        mess = await callback.message.answer(
            'В этом канале есть токены, если продолжить они будут удалены',
            reply_markup=keyboard
        )
        old_messages.append(mess.message_id)
        mess = await callback.message.answer('Выберите действие', reply_markup=cancel_keyboard())

        old_messages.append(mess.message_id)
        await state.update_data({'user_channel_pk': user_channel_pk})
        await state.update_data({'messages': old_messages})
        return
    await state.update_data({'messages': old_messages})
    callback.data = 'True'
    await delete_user_channel_handler(callback, state)


@logger.catch
async def delete_user_channel_handler(callback: CallbackQuery, state: FSMContext, **kwargs) -> None:
    """последний этап удаления канала """

    data: dict = await state.get_data()
    if callback.data == 'True':
        user_channel_pk: int = data.get('user_channel_pk')
        await DBI.delete_user_channel(user_channel_pk=user_channel_pk)
        await callback.message.answer("Канал удален.", reply_markup=user_menu_keyboard())
    else:
        await callback.message.answer('Удаление отменено', reply_markup=user_menu_keyboard())
        await callback.message.delete()
    old_messages = data.get('messages', [])
    for message_id in old_messages:
        try:
            await bot.delete_message(callback.message.chat.id, message_id=message_id)
        except aiogram.utils.exceptions.MessageToDeleteNotFound as err:
            logger.error(f"MessageToDeleteNotFound: {err}")
    await state.finish()


@logger.catch
async def set_token_name(message: Message, state: FSMContext) -> None:
    """Хэндлер для переименования токена """
    name = message.text
    data: dict = await state.get_data()
    token_pk = data.get('token_pk')
    await DBI.set_token_name(token_pk=token_pk, name=name)
    await message.answer("Токен переименован.", reply_markup=user_menu_keyboard())
    token_info = await DBI.get_info_by_token_pk(token_pk=token_pk)
    mess: str = (
        f"Имя токена: {token_info.token_name}"
        f"\nТокен: {token_info.token}"
        f"\nКанал: {token_info.channel_id}"
        f"\nДискорд id: {token_info.token_discord_id}"
        f"\nДискорд id напарника: {token_info.mate_discord_id}"
        f"\nКуллдаун канала: {token_info.cooldown} сек."
    )
    keyboard: 'InlineKeyboardMarkup' = InlineKeyboardMarkup(row_width=2)
    keyboard.add(InlineKeyboardButton(
        text="Удалить токен.", callback_data=f"del_token_{token_info.token_pk}"),
        InlineKeyboardButton(
            text="Переименовать токен.", callback_data=f"rename_token_{token_info.token_pk}"))
    await message.answer(mess, reply_markup=keyboard)
    await state.finish()


@logger.catch
def token_register_handlers(dp: Dispatcher) -> None:
    """
    Регистратор для функций данного модуля
    """
    dp.register_callback_query_handler(cancel_handler.callback_cancel_handler, Text(startswith=[
        "отмена", "cancel"], ignore_case=True), state="*")
    dp.register_callback_query_handler(start_create_channel_handler, Text(equals=[
        "new_channel"]), state=TokenStates.create_channel)
    dp.register_callback_query_handler(start_create_channel_handler, Text(equals=[
        "new_channel"]), state=TokenStates.select_channel)
    dp.register_callback_query_handler(ask_token_for_selected_channel_handler, state=TokenStates.select_channel)
    dp.register_message_handler(check_channel_and_add_token_handler, state=TokenStates.add_token)
    dp.register_message_handler(check_and_add_token_handler, state=TokenStates.check_token)
    dp.register_callback_query_handler(ask_channel_cooldown_handler, Text(startswith=[
        "set_cooldown_"]))
    dp.register_callback_query_handler(no_cooldown_enter_handler, Text(startswith=["endof"]))
    dp.register_callback_query_handler(delete_token_handler, Text(startswith=["del_token_"]))
    dp.register_callback_query_handler(rename_token_handler, Text(startswith=["rename_token_"]))
    # ---------channels--------------
    dp.register_message_handler(menu_channel_handler, Text(equals=["Каналы"]))
    dp.register_message_handler(list_channel_handler, Text(equals=[CHANNEL_MENU.rename]))
    dp.register_callback_query_handler(
        rename_channel_handler, state=UserChannelStates.select_user_channel_to_rename)
    dp.register_message_handler(
        set_user_channel_name, state=UserChannelStates.enter_name_for_user_channel)

    dp.register_message_handler(list_channel_handler_for_delete, Text(equals=[CHANNEL_MENU.delete]))
    dp.register_callback_query_handler(
        check_tokens_for_user_channel_handler, state=UserChannelStates.checks_tokens_for_user_channel)
    dp.register_callback_query_handler(
        delete_user_channel_handler, state=UserChannelStates.delete_for_user_channel)

    dp.register_message_handler(select_channel_handler, Text(equals=[CHANNEL_MENU.cooldown]))
    dp.register_callback_query_handler(
        ask_channel_cooldown_handler, state=TokenStates.add_channel_cooldown)
    dp.register_message_handler(
        add_channel_cooldown_handler, state=TokenStates.add_channel_cooldown)
    # ---------end channels----------

    dp.register_message_handler(set_token_name, state=TokenStates.set_name_for_token)
    dp.register_message_handler(info_tokens_handler, Text(equals=["Информация"]))
    dp.register_message_handler(select_channel_handler, Text(equals=['Добавить токен']))
