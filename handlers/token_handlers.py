from collections import namedtuple
from typing import List

from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove

from aiogram.dispatcher import FSMContext

from classes.request_sender import RequestSender
from states import TokenStates
from utils import check_is_int, send_report_to_admins
from classes.db_interface import DBI
from config import logger, Dispatcher, admins_list
from keyboards import user_menu_keyboard, cancel_keyboard, new_channel_key


@logger.catch
async def select_channel_handler(message: Message) -> None:
    """"""
    if await DBI.is_expired_user_deactivated(message):
        return
    telegram_id: str = str(message.from_user.id)
    channels: List[namedtuple] = await DBI.get_user_channels(telegram_id=telegram_id)
    await message.answer("В какой канал добавить токен?")
    if channels:
        for elem in channels:
            keyboard = InlineKeyboardMarkup(row_width=1).add(InlineKeyboardButton(
                text="Добавить сюда",
                callback_data=f"{elem.user_channel_pk}")
            )
            text: str = f"Имя канала: {elem.channel_name}\nСервер/канал: {elem.guild_id}/{elem.channel_id}"
            await message.answer(text, reply_markup=keyboard)
            await TokenStates.select_channel.set()

    else:
        await message.answer(
            "У вас нет ни одного канала. Сначала нужно создать новый канал и добавить в него токен.",
            reply_markup=await new_channel_key()
        )
        await TokenStates.create_channel.set()


@logger.catch
async def start_create_channel_handler(message: Message) -> None:
    """"""

    await message.answer(
        "Введите ссылку на канал в виде: "
        "https://discord.com/channels/932034587264167975/932034858906401842",
        reply_markup=cancel_keyboard()
    )
    await TokenStates.add_token.set()


@logger.catch
async def check_channel_and_add_token_handler(message: Message, state: FSMContext) -> None:
    """"""
    mess: str = message.text
    try:
        guild, channel = mess.rsplit('/', maxsplit=3)[-2:]
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
    """"""
    await message.answer("Проверяю данные.")
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

    proxy: str = await RequestSender().get_checked_proxy(telegram_id=message.from_user.id)
    if proxy == 'no proxies':
        text: str = "Ошибка прокси. Нет доступных прокси."
        await message.answer(text, reply_markup=ReplyKeyboardRemove())
        await send_report_to_admins(text)
        await state.finish()
        return

    result: dict = await RequestSender().check_token(token=token, proxy=proxy, channel=channel)
    if not result.get("success"):
        error_message: str = result.get("message")
        if error_message == 'bad proxy':
            await message.answer(error_message, reply_markup=user_menu_keyboard())
        elif error_message == 'bad token':
            await message.answer(
                f"Ваш токен {token} не прошел проверку в канале {channel}. "
                "\nЛибо канал не существует либо токен отсутствует данном канале, "
                "\nЛибо токен не рабочий."
                "\nВведите ссылку на канал заново:",

                reply_markup=cancel_keyboard()
            )
        else:
            logger.error("f: add_discord_token_handler: error: Don`t know why")
    await state.finish()


@logger.catch
def token_register_handlers(dp: Dispatcher) -> None:
    """
    Регистратор для функций данного модуля
    """
    dp.register_message_handler(select_channel_handler, commands=['add_token'])
    dp.register_message_handler(start_create_channel_handler, state=TokenStates.create_channel)
    dp.register_message_handler(check_channel_and_add_token_handler, state=TokenStates.add_token)
    dp.register_message_handler(check_and_add_token_handler, state=TokenStates.check_token)
