import json
from typing import Optional

import aiogram.utils.exceptions
from json import JSONDecodeError

from classes.db_interface import DBI
from config import logger, admins_list, bot
from keyboards import user_menu_keyboard


class ErrorsSender:
    """Отправляет сообщения об ошибках"""

    def __init__(self, answer: dict = None, proxy: str = '', token: str = '', telegram_id: str = ''):
        self._answer: dict = answer if answer else {}
        self._status: int = answer.get("status", 0)
        self._answer_data: str = answer.get("answer_data", {})
        self._proxy: str = proxy if proxy else 'no proxy'
        self._token: str = token if token else ''
        self._telegram_id: str = telegram_id if telegram_id else 'no telegram_id'
        self._code: Optional[int] = None

    @logger.catch
    async def handle_errors(self) -> dict:
        data = {}
        if self._answer_data:
            try:
                data: dict = json.loads(self._answer_data)
                if isinstance(data, dict):
                    self._code = data.get("code", 0)
            except JSONDecodeError as err:
                logger.error(
                    f"ErrorsSender: answer_handling: JSON ERROR: {err}"
                    f"\nAnswer data: {self._answer_data}"
                )
        if self._status == 200:
            self._answer.update(answer_data=data)
        else:
            await self.send_message_check_token()
            return {}
        return self._answer

    @logger.catch
    async def send_message_check_token(
            self,
            admins: bool = False,
            users: bool = True,
    ) -> None:
        error_message: str = (
            f"ErrorsSender get error:"
            f"\n\tTelegram_id: {self._telegram_id}"
            f"\n\tToken: {self._token}"
            f"\n\tProxy: {self._proxy}"
            f"\n\tError status: {self._status}"
            f"\n\tError data: {self._answer_data}"
        )
        logger.error(error_message)
        if self._status == -100:
            text: str = f'Произошла ошибка запроса. RequestSender._EXCEPTIONS: read the logs.'
            admins = True
            users = False
        elif self._status == 400:
            if self._code == 50035:
                text: str = f'Сообщение для ответа удалено из дискорд канала.'
                admins = False
            else:
                text: str = f'Ошибка 400.'
                admins = False
        elif self._status == 401:
            if self._code == 0:
                text: str = (
                    f"Токен не рабочий."
                    f"\nToken: {self._token}")
                if await DBI.delete_token(token=self._token):
                    text += f"\nТокен: {self._token} удален."
            else:
                text: str = (
                    "Произошла ошибка данных."
                    "\nУбедитесь, что вы ввели верные данные. Код ошибки - 401."
                )
            admins = False
        elif self._status == 403:
            if self._code == 50013:
                text: str = (
                    "Не могу отправить сообщение для токена. (Ошибка 403 - 50013)"
                    "Токен в муте."
                )
                if self._token:
                    text += f"\nToken: {self._token}"
            elif self._code == 50001:
                text: str = (
                    "Не могу отправить сообщение для токена. (Ошибка 403 - 50001)"
                    "Токен забанили."
                    f"\nФормирую новые пары."
                )
                if await DBI.delete_token(token=self._token):
                    text += f"\nТокен: {self._token} удален."
                await DBI.form_new_tokens_pairs(telegram_id=self._telegram_id)
            else:
                text: str = f"Ошибка {self._status} Code: {self._code}"
        elif self._status == 404:
            if self._code == 10003:
                text: str = "Ошибка отправки сообщения. Неверный канал. (Ошибка 404 - 10003)"
                if self._token:
                    text += f"\nToken: {self._token}"
            else:
                text: str = f"Ошибка {self._status}"
        elif self._status == 407:
            text = (
                f'Ошибка прокси: {self._proxy}. '
                f'\nОбратитесь к администратору. Код ошибки 407')
            users = True
            admins = True
        elif self._status == 500:
            text = f"Внутренняя ошибка сервера Дискорда. Код ошибки - 500."
            admins = True
        else:
            text = 'Unrecognised error!'
            users = False
            admins = True

        if text:
            if users and self._telegram_id:
                await self.errors_report(text=text)
            if admins:
                await self.send_report_to_admins(text)

    @logger.catch
    async def errors_report(self, text: str) -> None:
        """Errors report"""

        logger.error(f"Errors report: {text}")
        try:
            await bot.send_message(
                chat_id=self._telegram_id, text=text, reply_markup=user_menu_keyboard())
        except aiogram.utils.exceptions.ChatNotFound:
            logger.error(f"Chat {self._telegram_id} not found")

    @classmethod
    @logger.catch
    async def send_report_to_admins(cls, text: str) -> None:
        """Отправляет сообщение в телеграме всем администраторам из списка"""

        text = f'[Рассылка][Superusers]: {text}'
        for admin_id in admins_list:
            try:
                await bot.send_message(
                    chat_id=admin_id, text=text, reply_markup=user_menu_keyboard())
            except aiogram.utils.exceptions.ChatNotFound as err:
                logger.error(f"Не смог отправить сообщение пользователю {admin_id}.", err)

    @classmethod
    @logger.catch
    async def proxy_not_found_error(cls):
        text: str = "Нет доступных прокси."
        await cls.send_report_to_admins(text)
