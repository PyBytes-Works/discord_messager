"""Модуль с основными обработчиками команд и сообщений"""
from aiogram.types import Message
from aiogram.dispatcher.filters import Text

from classes.keyboards_classes import StartMenu, MailerMenu, GrabberMenu
from config import logger, Dispatcher
from classes.db_interface import DBI
from _resources import __version__


@logger.catch
async def activate_valid_user_handler(message: Message):
    """Активирует пользователя если он продлил оплату при команде /start"""

    user_telegram_id: str = str(message.from_user.id)
    is_user_exists: bool = await DBI.get_user_by_telegram_id(telegram_id=user_telegram_id)
    is_subscribe_active: bool = await DBI.is_subscribe_active(telegram_id=user_telegram_id)
    is_user_active: bool = await DBI.user_is_active(telegram_id=user_telegram_id)
    if is_user_exists and is_subscribe_active:
        if is_user_active:
            await message.answer("Добро пожаловать.", reply_markup=StartMenu.keyboard())
            return
        await DBI.activate_user(telegram_id=user_telegram_id)
        await message.answer("Аккаунт активирован.", reply_markup=StartMenu.keyboard())
        logger.info(f"Account {user_telegram_id} activated.")


@logger.catch
async def menu_selector_message(message: Message) -> None:
    """"""
    spam = {
        StartMenu.mailer: MailerMenu.keyboard(),
        StartMenu.grabber: GrabberMenu.keyboard(),

    }
    await message.answer(f'Выберите команду:', reply_markup=spam[message.text])


@logger.catch
async def default_message(message: Message) -> None:
    """Ответ на любое необработанное действие активного пользователя."""

    user_telegram_id: str = str(message.from_user.id)
    is_user_exists: bool = await DBI.get_user_by_telegram_id(telegram_id=user_telegram_id)
    if is_user_exists:
        if not await DBI.is_expired_user_deactivated(message):
            await message.answer(f'Текущая версия: {__version__}', reply_markup=StartMenu.keyboard())


@logger.catch
def main_register_handlers(dp: Dispatcher) -> None:
    """
    Регистратор для функций данного модуля
    """

    dp.register_message_handler(activate_valid_user_handler, commands=["start"])
    dp.register_message_handler(menu_selector_message, Text(
        equals=[StartMenu.mailer, StartMenu.grabber]))
    dp.register_message_handler(default_message)
