from collections import namedtuple
from typing import List

from aiogram.dispatcher.filters import Text
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from aiogram.dispatcher import FSMContext

from classes.request_classes import GetMe, ProxyChecker, TokenChecker
from handlers import main_handlers
from states import TokenStates
from utils import check_is_int
from classes.db_interface import DBI
from classes.errors_sender import ErrorsSender
from config import logger, Dispatcher
from keyboards import (
    user_menu_keyboard, cancel_keyboard, new_channel_key, yes_no_buttons,
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
    keyboard = InlineKeyboardMarkup(row_width=1)
    if not channels:
        await message.answer(
            "У вас нет ни одного канала. Сначала нужно создать новый канал и добавить в него токен.",
            reply_markup=cancel_keyboard()
        )
        # await TokenStates.create_channel.set()
        # return
    if message.text == 'Установить кулдаун':
        for elem in channels:
            keyboard.add(InlineKeyboardButton(
                text="Добавить сюда",
                callback_data=f"{elem.user_channel_pk}")
            )
            text: str = f"Имя канала: {elem.channel_name}\nСервер/канал: {elem.guild_id}/{elem.channel_id}"
            await message.answer(text, reply_markup=keyboard)
            await message.answer("Для какого канала установить кулдаун?", reply_markup=cancel_keyboard())
            await TokenStates.add_channel_cooldown.set()
    elif message.text == "Добавить токен":
        for elem in channels:
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
        logger.error("F: add_channel_handler error: err", err)
        guild: str = ''
        channel: str = ''
    guild: str = str(check_is_int(guild))
    channel: str = str(check_is_int(channel))
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
            "\n Повторите ввод токена.",
            reply_markup=cancel_keyboard()
        )
        return

    data: dict = await state.get_data()
    channel: int = data.get('channel')
    guild: int = data.get('guild')
    user_channel_pk: int = int(data.get("user_channel_pk", 0))
    if user_channel_pk:
        channel: int = await DBI.get_channel(user_channel_pk=user_channel_pk)

    proxy: str = await ProxyChecker().get_checked_proxy(telegram_id=telegram_id)
    if proxy == 'no proxies':
        await ErrorsSender.errors_report(telegram_id=telegram_id, text="Ошибка прокси. Нет доступных прокси.")
        await state.finish()
        return

    discord_id: str = await GetMe().get_discord_id(token=token, proxy=proxy)
    await message.answer("Получаю дискорд id.")
    if not discord_id:
        error_text: str = (f"Не смог определить discord_id для токена:"
                           f"\nToken: [{token}]"
                           f"\nGuild/channel: [{guild}: {channel}]")
        await ErrorsSender.errors_report(telegram_id=telegram_id, text=error_text)
        await state.finish()
        return
    if await DBI.check_token_by_discord_id(discord_id=discord_id):
        error_text: str = 'Токен с таким дискорд id уже сущестует в базе'
        await ErrorsSender.errors_report(telegram_id=telegram_id, text=error_text)
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
        user_channel_pk: int = await DBI.add_user_channel(telegram_id=telegram_id, channel_id=channel, guild_id=guild)
        await message.answer(f"Создаю канал {channel}")
        if not user_channel_pk:
            await ErrorsSender.errors_report(
                telegram_id=telegram_id,
                text=f"Не смог добавить канал:\n{telegram_id}:{channel}:{guild}"
            )
            await state.finish()
            return
    await message.answer(f"Канал {channel} создан."
                         f"Добавляю токен в канал...\n")

    if not await DBI.add_token_by_telegram_id(
            telegram_id=telegram_id, token=token, discord_id=discord_id, user_channel_pk=user_channel_pk
    ):
        error_text: str = (f"Не добавить токен:"
                           f"\nToken: [{token}]"
                           f"\nGuild/channel: [{guild}: {channel}]")
        await ErrorsSender.errors_report(telegram_id=telegram_id, text=error_text)
        await state.finish()
        return
    await message.answer(
        "Токен удачно добавлен."
        "Хотите ввести кулдаун для данного канала?",
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

    user_channel_pk: int = check_is_int(callback.data.rsplit("_", maxsplit=1)[-1])
    await state.update_data(user_channel_pk=user_channel_pk)
    await callback.message.answer("Введите время кулдауна в минутах:", reply_markup=cancel_keyboard())
    await TokenStates.add_channel_cooldown.set()
    await callback.answer()


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
    user_channel_pk: int = int(data.get("user_channel_pk"))
    if not await DBI.update_user_channel_cooldown(user_channel_pk=user_channel_pk, cooldown=cooldown):
        error_text: str = (f"Не смог установить кулдаун для канала:"
                           f"\nuser_channel_pk: [{user_channel_pk}: cooldown: {cooldown}]")
        await ErrorsSender.errors_report(telegram_id=str(message.from_user.id), text=error_text)
        await state.finish()
        return
    await message.answer("Кулдаун установлен.", reply_markup=user_menu_keyboard())
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
        keyboard: 'InlineKeyboardMarkup' = InlineKeyboardMarkup(row_width=1)
        keyboard.add(InlineKeyboardButton(
            text="Удалить токен.", callback_data=f"del_token_{token_info.token_pk}"))
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
    else:
        token_pk: int = int(callback.data.rsplit('_', maxsplit=1)[-1])
        await DBI.delete_token_by_pk(token_pk=token_pk)
        await callback.message.answer("Токен удален.", reply_markup=user_menu_keyboard())
        await callback.message.delete()
        await state.finish()
    await callback.answer()


@logger.catch
async def no_cooldown_enter_handler(callback: CallbackQuery) -> None:
    """Хэндлер для нажатия на кнопку "Нет" при выборе "Установить кулдаун или нет """

    await callback.message.answer("Установлен кулдаун по умолчанию: 1 минута.", reply_markup=user_menu_keyboard())
    await callback.answer()


@logger.catch
def token_register_handlers(dp: Dispatcher) -> None:
    """
    Регистратор для функций данного модуля
    """
    dp.register_callback_query_handler(main_handlers.callback_cancel_handler, Text(startswith=["отмена", "cancel"], ignore_case=True), state="*")
    dp.register_callback_query_handler(start_create_channel_handler, Text(equals=[
        "new_channel"]), state=TokenStates.select_channel)
    dp.register_callback_query_handler(ask_token_for_selected_channel_handler, state=TokenStates.select_channel)
    dp.register_callback_query_handler(start_create_channel_handler, Text(equals=[
        "new_channel"]), state=TokenStates.create_channel)
    dp.register_message_handler(check_channel_and_add_token_handler, state=TokenStates.add_token)
    dp.register_message_handler(check_and_add_token_handler, state=TokenStates.check_token)
    dp.register_callback_query_handler(ask_channel_cooldown_handler, Text(startswith=[
        "set_cooldown_"]))
    dp.register_callback_query_handler(no_cooldown_enter_handler, Text(startswith=["endof"]))
    dp.register_callback_query_handler(ask_channel_cooldown_handler, state=TokenStates.add_channel_cooldown)
    dp.register_message_handler(add_channel_cooldown_handler, state=TokenStates.add_channel_cooldown)
    dp.register_callback_query_handler(delete_token_handler, Text(startswith=["del_token_"]))
    dp.register_message_handler(info_tokens_handler, Text(equals=["Информация"]))
    dp.register_message_handler(select_channel_handler, Text(equals=["Установить кулдаун"]))
    dp.register_message_handler(select_channel_handler, Text(equals=['Добавить токен']))
