import json
from typing import Optional

import aiogram.utils.exceptions
from json import JSONDecodeError

from classes.db_interface import DBI
from classes.token_datastorage import TokenData
from config import logger, admins_list, bot


# TODO Превратить в chain. Добавить обработку datastore

class ErrorsReporter:
    """Отправляет сообщения об ошибках"""

    def __init__(
            self,
            answer: dict = None,
            proxy: str = '',
            token: str = '',
            telegram_id: str = '',
            datastore=None
    ) -> None:
        self._answer: dict = answer if answer else {}
        self._status: int = answer.get("status", 0) if answer else 0
        self._answer_data: str = answer.get("answer_data", {}) if answer else {}
        self._proxy: str = proxy if proxy else ''
        self._token: str = token if token else ''
        self._telegram_id: str = telegram_id if telegram_id else ''
        self._code: Optional[int] = None
        self._datastore: 'TokenData' = datastore
        self._answer_data_dict: dict = {}

    @logger.catch
    async def handle_errors(self) -> dict:
        """Parse status and data from answer"""

        data = {}
        if self._answer_data and not self._answer_data.startswith('<!doctype html>'):
            try:
                data: dict = json.loads(self._answer_data)
                if isinstance(data, dict):
                    self._code = data.get("code", 0)
                    self._answer_data_dict = data
            except JSONDecodeError as err:
                logger.error(
                    f"ErrorsSender: answer_handling: JSON ERROR: {err}"
                    f"\nStatus: {self._status}"
                    f"\nAnswer data: {self._answer_data}"
                )
        self._answer.update(answer_data=data)
        if self._status not in range(200, 205):
            await self.send_message_check_token()
        return self._answer

    @logger.catch
    async def send_message_check_token(
            self,
            admins: bool = False,
            users: bool = True,
    ) -> None:
        """Sending error messages"""

        text: str = ''
        if self._status == 0:
            # See logs
            pass
        elif self._status == -99:
            text: str = f'Ошибка таймаута'
            admins = True
            users = False
        elif self._status == -100:
            text: str = f'Произошла ошибка запроса. RequestSender._EXCEPTIONS: read the logs.'
            admins = True
            users = False
        elif self._status == 400:
            if self._code == 50035:
                text: str = f'Сообщение для ответа удалено из дискорд канала.'
            else:
                text: str = f'Ошибка 400.'
        elif self._status == 401:
            if self._code == 0:
                text: str = f"Токен не рабочий."
                if await DBI.delete_token(token=self._token):
                    text += f"\nТокен удален."
            else:
                text: str = (
                    "Произошла ошибка данных."
                    "\nУбедитесь, что вы ввели верные данные. Код ошибки - 401."
                )
        elif self._status == 403:
            if self._code == 50013:
                text: str = (
                    "Не могу отправить сообщение для токена. (Ошибка 403 - 50013)"
                    "\nТокен в муте."
                )
                if await DBI.delete_token(token=self._token):
                    text += f"\nТокен удален."
            elif self._code == 50001:
                text: str = (
                    "Не могу отправить сообщение для токена. (Ошибка 403 - 50001)"
                    "\nТокен забанили."
                    f"\nФормирую новые пары."
                )
                if await DBI.delete_token(token=self._token):
                    text += f"\nТокен удален."
            else:
                text: str = f"Ошибка {self._status} Code: {self._code}"
        elif self._status == 404:
            if self._code == 10003:
                text: str = "Ошибка отправки сообщения. Неверный канал. (Ошибка 404 - 10003)"
            else:
                text: str = f"Ошибка {self._status}"
        elif self._status == 407:
            text = (
                f'Ошибка прокси.'
                f'\nОбратитесь к администратору. Код ошибки 407')
            admins = True
        elif self._status == 429:
            if self._code == 20016:
                cooldown: int = int(self._answer_data_dict.get("retry_after"))
                if cooldown:
                    cooldown += self._datastore.cooldown
                    await DBI.update_user_channel_cooldown(
                        user_channel_pk=self._datastore.user_channel_pk, cooldown=cooldown)
                    self._datastore.delay = cooldown
                await self.errors_report(
                    text=(
                        "Для данного токена сообщения отправляются чаще, чем разрешено в канале."
                        f"\nToken: {self._datastore.token}"
                        f"\nГильдия/Канал: {self._datastore.guild}/{self._datastore.channel}"
                        f"\nВремя скорректировано. Кулдаун установлен: {cooldown} секунд"
                    )
                )
            elif self._code == 40062:
                text: str = (
                    f"Токену необходимо дополнительная верификация в дискорде (по номеру телефона):"
                )
                if await DBI.delete_token(token=self._token):
                    text += f"\nТокен удален."
        elif self._status == 500:
            text = (f"Внутренняя ошибка сервера Дискорда. Код ошибки - [{self._status}]"
                    f"\nСлишком большая нагрузка на канал")
            admins = True
        elif self._status == 504:
            text = f"Внутренняя ошибка сервера Дискорда. Код ошибки - [{self._status}]"
            users = False
            admins = True
        else:
            text = f'Unrecognised error! {self._status} {self._code}'
            users = False
            admins = True
        if text:
            if self._datastore:
                self._telegram_id = self._datastore.telegram_id
                self._proxy = self._datastore.proxy
                self._token = self._datastore.token_name
                text += f"Channel: {self._datastore.channel}"
            if self._telegram_id:
                text += f"\nTelegram_ID: {self._telegram_id}"
            if self._token:
                text += f"\nToken: {self._token}"
            if self._proxy:
                text += f"\nProxy [{self._proxy}]"
            if users and self._telegram_id:
                await self.errors_report(text=text)
            if admins:
                await self.send_report_to_admins(text)
        error_message: str = (
            f"ErrorsSender get error:"
            f"\n\tTelegram_id: {self._telegram_id}"
            f"\n\tToken: {self._token}"
            f"\n\tProxy: {self._proxy}"
            f"\n\tError status: {self._status}"
            f"\n\tError data: {self._answer_data}"
        )
        logger.error(error_message)

    @logger.catch
    async def errors_report(self, text: str) -> None:
        """Errors report"""

        logger.error(f"Errors report: {text}")
        try:
            await bot.send_message(
                chat_id=self._telegram_id, text=text)
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
                    chat_id=admin_id, text=text)
            except aiogram.utils.exceptions.ChatNotFound as err:
                logger.error(f"Не смог отправить сообщение пользователю {admin_id}.", err)

    @classmethod
    @logger.catch
    async def proxy_not_found_error(cls):
        text: str = "Нет доступных прокси."
        await cls.send_report_to_admins(text)
