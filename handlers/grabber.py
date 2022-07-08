"""Модуль с обработчиками команд Grabber`a"""
from aiogram.dispatcher.filters import Text
from aiogram.types import Message
from aiogram.dispatcher import FSMContext

from discord_grabber import TokenGrabber


from config import logger, Dispatcher, settings
from classes.keyboards_classes import GrabberMenu
from states import GrabberStates
from pydantic import BaseModel, EmailStr, BaseSettings


class GrabberSettings(BaseSettings):
    ANTICAPTCHA_KEY: str = ''
    WEB_URL: str = ''
    EMAIL: EmailStr = ''
    PASSWORD: str = ''
    DEBUG: bool = False


class UserModel(BaseModel):
    email: EmailStr
    password: str


grabber_settings = GrabberSettings(_env_file='.env', _env_file_encoding='utf-8')


@logger.catch
async def login_password_handler(message: Message):
    """"""

    await message.answer("Введите email пользователя и пароль через `:`"
                         "\nНапример: user@google.com:password", reply_markup=GrabberMenu.keyboard())
    await GrabberStates.enter_data.set()


@logger.catch
async def validate_login_password_handler(message: Message, state: FSMContext):
    """"""

    email, password = message.text.split(':')
    data = dict(
        email=email, password=password, anticaptcha_key=grabber_settings.ANTICAPTCHA_KEY,
        web_url=grabber_settings.WEB_URL, log_level=settings.LOGGING_LEVEL
    )
    token_data = TokenGrabber(**data).get_token()
    logger.info(token_data)
    token: str = token_data.get("token")
    await message.answer(f"Token: {token}", reply_markup=GrabberMenu.keyboard())
    await state.finish()


@logger.catch
def grabber_register_handlers(dp: Dispatcher) -> None:
    """
    Регистратор для функций данного модуля
    """

    dp.register_message_handler(login_password_handler, Text(equals=[GrabberMenu.get_token]))
    dp.register_message_handler(validate_login_password_handler, state=GrabberStates.enter_data)
