"""Модуль с обработчиками команд Grabber`a"""
import asyncio
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
async def enter_invite_link_handler(message: Message):
    """"""

    await message.answer(
        "Введите ссылку-приглашение: "
        "\nНапример: https://discord.gg/cf3f9sD9",
        disable_web_page_preview=True,
        reply_markup=JoinerMenu.keyboard())
    await JoinerStates.enter_link.set()


def _check_invite_link(invite_link: str):
    if invite_link.startswith(('https://discord.com/invite/', 'https://discord.gg')):
        return invite_link
    return ''


@logger.catch
async def enter_tokens_handler(message: Message, state: FSMContext):
    """"""
    invite_link: str = _check_invite_link(message.text.strip())
    if not invite_link:
        await message.answer(
            "Ссылка должна быть в формате:"
            "\nhttps://discord.gg/cf3f9sD9",
            disable_web_page_preview=True,
            reply_markup=JoinerMenu.keyboard())
        return
    await state.update_data(invite_link=invite_link)
    await message.answer(
        "Введите токены через пробел:"
        "\nНапример: Токен1 Токен2 Токен3",
        reply_markup=JoinerMenu.keyboard())
    await JoinerStates.enter_tokens.set()


@logger.catch
async def add_token_by_invite_link_handler(message: Message, state: FSMContext):
    """"""
    data = await state.get_data()
    invite_link = data['invite_link']
    tokens: list[str] = message.text.strip().split()
    proxy_addr: namedtuple = await DBI.get_low_used_proxy()

    proxy = {
        "http": f"http://{settings.PROXY_USER}:{settings.PROXY_PASSWORD}@{proxy_addr.proxy}/",
        "https": f"http://{settings.PROXY_USER}:{settings.PROXY_PASSWORD}@{proxy_addr.proxy}/"
    }

    data = dict(
        invite_link=invite_link, log_level=settings.LOGGING_LEVEL,
        user_agent=user_agent, proxy=proxy
    )
    success = errors = 0
    tasks = []
    for token in tokens:
        await message.answer(f"Добавляю токен:\n{token}")
        data["token"] = token
        joiner = DiscordJoiner(**data)
        tasks.append(asyncio.create_task(joiner.join()))

    responses = await asyncio.gather(*tasks)
    for result in responses:
        if result['success']:
            text = f"Токен {result['token']} добавлен."
            success += 1
        else:
            text = f'Токен НЕ добавлен: {result["message"]}'
            errors += 1
        await message.answer(text)

    await message.answer(
        f"Итого:"
        f"\nТокенов: {len(tokens)}"
        f"\nДобавлено: {success}"
        f"\nНе добавлено: {errors}",
        reply_markup=JoinerMenu.keyboard()
    )

    await state.finish()


@logger.catch
def joiner_register_handlers(dp: Dispatcher) -> None:
    """
    Регистратор для функций данного модуля
    """

    dp.register_message_handler(enter_invite_link_handler, Text(equals=[JoinerMenu.add_tokens]))
    dp.register_message_handler(enter_tokens_handler, state=JoinerStates.enter_link)
    dp.register_message_handler(add_token_by_invite_link_handler, state=JoinerStates.enter_tokens)
