"""Модуль с обработчиками команд Grabber`a"""
from collections import namedtuple

from aiogram.dispatcher.filters import Text
from aiogram.types import Message
from aiogram.dispatcher import FSMContext

from classes.db_interface import DBI
from config import logger, Dispatcher, settings, user_agent
from classes.keyboards_classes import JoinerMenu
from states import JoinerStates
from discord_joiner.joiner import DiscordJoiner


@logger.catch
async def enter_token_handler(message: Message):
    """"""

    if not await DBI.get_user_tokens_amount(message.from_user.id):
        await message.answer(
            "У вас нет ни одного токена. Сначала добавьте хотя бы один.",
            reply_markup=JoinerMenu.keyboard())
        return
    await message.answer(
        "Введите ссылку-приглашение: "
        "\nНапример: https://discord.gg/cf3f9sD9",
        reply_markup=JoinerMenu.keyboard())
    await JoinerStates.enter_data.set()


@logger.catch
async def add_token_by_invite_link_handler(message: Message, state: FSMContext):
    """"""

    invite_link = message.text.strip()
    tokens_info: list[namedtuple] = await DBI.get_all_tokens_info(message.from_user.id)
    token_proxy = tokens_info[0].proxy
    tokens: list[str] = [elem.token for elem in tokens_info]

    proxy = {
        "http": f"http://{settings.PROXY_USER}:{settings.PROXY_PASSWORD}@{token_proxy}/",
    }

    data = dict(
        invite_link=invite_link, log_level=settings.LOGGING_LEVEL,
        user_agent=user_agent, proxy=proxy
    )
    success = errors = 0
    for token in tokens:
        await message.answer(f"Добавляю токен:\n{token}")
        data["token"] = token
        result: dict = await DiscordJoiner(**data).join()
        if result['success']:
            text = f"Токен {token} добавлен."
            success += 1
        else:
            text = f'Токен НЕ добавлен: {result["message"]}'
            errors += 1
        await message.answer(text)

    await message.answer(
        f"Итого:"
        f"\nТокенов: {len(tokens)}"
        f"\nДобавлено: {success}"
        f"\nНе добавлено: {errors}"
    )

    await state.finish()


@logger.catch
def joiner_register_handlers(dp: Dispatcher) -> None:
    """
    Регистратор для функций данного модуля
    """

    dp.register_message_handler(enter_token_handler, Text(equals=[JoinerMenu.add_tokens]))
    dp.register_message_handler(add_token_by_invite_link_handler, state=JoinerStates.enter_data)
