"""Модуль с обработчиками команд Grabber`a"""
import asyncio

import pydantic
from aiogram.dispatcher.filters import Text
from aiogram.types import Message
from aiogram.dispatcher import FSMContext

from discord_grabber import TokenGrabber
from discord_grabber.exceptions import CaptchaAPIkeyError

from classes.errors_reporter import ErrorsReporter
from config import logger, Dispatcher, settings, user_agent
from classes.keyboards_classes import GrabberMenu, BaseMenu
from states import GrabberStates
from pydantic import BaseModel, EmailStr, BaseSettings


class GrabberSettings(BaseSettings):
    ANTICAPTCHA_KEY: str = ''
    TWO_CAPTCHA_KEY: str = ''
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
async def enter_accounts_data_handler(message: Message, state: FSMContext):
    """"""

    accounts: list[str, ...] = message.text.strip().split()
    proxy = f"http://{settings.PROXY_USER}:{settings.PROXY_PASSWORD}@{settings.DEFAULT_PROXY}/"
    proxy = ''
    proxy_ip, proxy_port = settings.DEFAULT_PROXY.split(':')
    data = dict(
        anticaptcha_key=grabber_settings.ANTICAPTCHA_KEY,
        log_level=settings.LOGGING_LEVEL, proxy=proxy, user_agent=user_agent,
        max_tries=grabber_settings.MAX_CAPTCHA_TRIES, proxy_ip=proxy_ip, proxy_port=proxy_port,
        proxy_user=settings.PROXY_USER, proxy_password=settings.PROXY_PASSWORD, verbose=1
    )
    tasks = []
    for account in accounts:
        user_data: list[str, str] = account.strip().split(':')
        if len(user_data) != 2:
            error_message = ("Вы ввели неверные данные."
                             "\nВведите email пользователя и пароль через `:`"
                             "\nНапример: user@google.com:password")
            await message.answer(error_message, reply_markup=GrabberMenu.keyboard())
            continue
        email, password = user_data
        data.update(email=email, password=password)
        try:
            grabber = TokenGrabber(**data)
            tasks.append(asyncio.create_task(grabber.get_token()))
        except pydantic.error_wrappers.ValidationError as err:
            logger.error(err)
            await message.answer(f'Validation error: {err}', reply_markup=GrabberMenu.keyboard())

    await message.answer(
        "Получаю данные, ожидайте ответа..."
        f"\nВ случае необходимости прохождения капчи или подтверждения по почте это займет время..."
    )
    responses: tuple = await asyncio.gather(*tasks)
    for token_data in responses:
        email: str = token_data.get('email')
        text = f"Email: {email}"
        token: str = token_data.get("token")
        if token:
            text += f'\nToken:\n{token}'
        else:
            error_text = token_data.get('error')
            if error_text == CaptchaAPIkeyError().text:
                await ErrorsReporter.send_report_to_admins(error_text)
            text += f"\nError: {error_text}"
        await message.answer(text, reply_markup=GrabberMenu.keyboard())

    await state.finish()


@logger.catch
def grabber_register_handlers(dp: Dispatcher) -> None:
    """
    Регистратор для функций данного модуля
    """

    dp.register_message_handler(login_password_handler, Text(equals=[GrabberMenu.get_token]))
    dp.register_message_handler(enter_accounts_data_handler, state=GrabberStates.enter_data)
