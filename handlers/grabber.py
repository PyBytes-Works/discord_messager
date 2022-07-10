"""Модуль с обработчиками команд Grabber`a"""
import pydantic
from aiogram.dispatcher.filters import Text
from aiogram.types import Message
from aiogram.dispatcher import FSMContext

# from discord_grabber import TokenGrabber
from classes.grabber_class import TokenGrabber
from config import logger, Dispatcher, settings, user_agent
from classes.keyboards_classes import GrabberMenu, BaseMenu
from states import GrabberStates
from pydantic import BaseModel, EmailStr, BaseSettings


class GrabberSettings(BaseSettings):
    ANTICAPTCHA_KEY: str = ''
    WEB_URL: str = ''
    EMAIL: EmailStr = ''
    PASSWORD: str = ''
    DEBUG: bool = False
    MAX_CAPTCHA_TRIES: int = 12


class UserModel(BaseModel):
    email: EmailStr
    password: str


grabber_settings = GrabberSettings(_env_file='.env', _env_file_encoding='utf-8')


@logger.catch
async def login_password_handler(message: Message):
    """"""

    await message.answer(
        "Введите email пользователя и пароль через `:`"
        "\nНапример: user@google.com:password",
        reply_markup=BaseMenu.keyboard())
    await GrabberStates.enter_data.set()


@logger.catch
async def validate_login_password_handler(message: Message, state: FSMContext):
    """"""
    error_message = ("Вы ввели неверные данные."
                     "\nВведите email пользователя и пароль через `:`"
                     "\nНапример: user@google.com:password")
    user_data = message.text.strip().split(':')
    if len(user_data) != 2:
        await message.answer(error_message, reply_markup=GrabberMenu.keyboard())
        return
    email, password = user_data
    proxy = f"http://{settings.PROXY_USER}:{settings.PROXY_PASSWORD}@{settings.DEFAULT_PROXY}/"
    data = dict(
        email=email, password=password, anticaptcha_key=grabber_settings.ANTICAPTCHA_KEY,
        web_url=grabber_settings.WEB_URL, log_level=settings.LOGGING_LEVEL,
        user_agent=user_agent, proxy=proxy,
        max_tries=grabber_settings.MAX_CAPTCHA_TRIES
    )
    captcha_total_time: int = 10 * grabber_settings.MAX_CAPTCHA_TRIES
    try:
        logger.debug(data)
        await message.answer(
            "Получаю данные, ожидайте ответа..."
            f"\nВ случае необходимости прохождения капчи "
            f"время ожидания составит до {captcha_total_time} секунд..."
        )
        token_data: dict = await TokenGrabber(**data).get_token()
        logger.info(token_data)
    except pydantic.error_wrappers.ValidationError as err:
        logger.error(err)
        await message.answer(error_message, reply_markup=GrabberMenu.keyboard())
        return

    token: str = token_data.get("token")
    text = f"Token:\n{token}"
    if not token:
        text = f"Error: {token_data.get('error')}"
    await message.answer(text, reply_markup=GrabberMenu.keyboard())

    await state.finish()


@logger.catch
def grabber_register_handlers(dp: Dispatcher) -> None:
    """
    Регистратор для функций данного модуля
    """

    dp.register_message_handler(login_password_handler, Text(equals=[GrabberMenu.get_token]))
    dp.register_message_handler(validate_login_password_handler, state=GrabberStates.enter_data)
