import json
from typing import Optional

import aiogram.utils.exceptions
from json import JSONDecodeError

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
        self._answer_data: str = answer.get("answer_data", '')
        self._proxy: str = proxy if proxy else ''
        self._token: str = token if token else ''
        self._telegram_id: str = telegram_id if telegram_id else ''
        self._code: Optional[int] = None
        self.datastore: 'TokenData' = datastore
        self._answer_data_dict: dict = {}

    @logger.catch
    async def handle_errors(self) -> dict:
        """Parse status and data from answer"""

        data = {}
        if self._answer_data:
            if self._answer_data.startswith('<'):
                self._answer_data = 'some HTML answer'
            else:
                try:
                    data: dict = json.loads(self._answer_data)
                    if isinstance(data, dict):
                        self._code = data.get("code", 0)
                        self._answer_data_dict: dict = data
                except JSONDecodeError as err:
                    logger.error(
                        f"\n{self.handle_errors.__qualname__}: JSON ERROR: {err}"
                        f"\nStatus: {self._status}"
                        f"\nAnswer data: {self._answer_data}"
                    )
        self._answer.update(answer_data=data)
        if self._status not in range(200, 205):
            await self.errors_manager()
        return self._answer

    @logger.catch
    async def _set_datastore_delete_token(self) -> None:
        if self.datastore:
            self.datastore.delete_token()

    @logger.catch
    async def errors_manager(
            self,
            admins: bool = False,
            users: bool = True,
    ) -> None:
        """Sending error messages"""

        text: str = ''
        if self._status == 0:
            # See logs.
            pass
        elif self._status == -96:
            text: str = f'Ошибка ServerDisconnectedError ПРОКСИ НЕ РАБОТАЕТ!!!'
            admins = True
            users = False
        elif self._status == -97:
            text: str = f'Ошибка TooManyRedirects.'
            admins = True
            users = False
        elif self._status == -98:
            text: str = f'Ошибка ClientOSError (возникает при частых запросах)'
            admins = True
            users = False
        elif self._status == -99:
            text: str = f'Ошибка таймаута. Проверьте прокси.'
            admins = True
            users = False
        elif self._status == -100:
            text: str = (f'Произошла ошибка RequestSender. read the logs.'
                         f'Код ошибки [-100]')
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
                await self._set_datastore_delete_token()
            else:
                text: str = (
                    "Произошла ошибка данных."
                    "\nУбедитесь, что вы ввели верные данные. Код ошибки - 401."
                )
        elif self._status == 403:
            if self._code == 50001:
                text: str = (
                    "Не могу отправить сообщение для токена. (Ошибка 403 - 50001)"
                    "\nТокен забанили."
                    f"\nФормирую новые пары."
                )
            elif self._code == 40002:
                text: str = (
                    "Необходимо подтвердить учетную запись дискорда."
                    "(Ошибка 403 - 40002)"
                )
            elif self._code == 50013:
                text: str = (
                    "Не могу отправить сообщение для токена. (Ошибка 403 - 50013)"
                    "\nТокен в муте."
                )
            else:
                text: str = f"Ошибка {self._status} Code: {self._code}"
            await self._set_datastore_delete_token()

        elif self._status == 404:
            if self._code == 10003:
                text: str = "Ошибка отправки сообщения. Неверный канал. (Ошибка 404 - 10003)"
            else:
                text: str = f"Ошибка {self._status}"
        elif self._status == 407:
            text = (
                f'Ошибка прокси.'
                f'\nОбратитесь к администратору. Код ошибки 407')
            users = False
            admins = True
        elif self._status == 429:
            if self._code == 20016:
                cooldown: int = int(self._answer_data_dict.get("retry_after")) + 1
                if cooldown:
                    cooldown += self.datastore.cooldown
                    self.datastore.new_delay = cooldown
            elif self._code == 40062:
                text: str = (
                    f"Ошибка 429 код ошибки 40062."
                )
        elif self._status == 500:
            text = (f"Внутренняя ошибка сервера Дискорда. Код ошибки - [{self._status}]"
                    f"\nСлишком большая нагрузка на канал")
        elif self._status == 502:
            text = f"Внутренняя ошибка сервера Дискорда. Код ошибки - 502 Bad Gateway"
        elif self._status == 503:
            text = f"Код ошибки - 503"
        elif self._status == 504:
            text = f"Внутренняя ошибка сервера Дискорда. Код ошибки - [{self._status}]"
        else:
            text = f'Unrecognised error! {self._status} {self._code}'
            users = False
            admins = True
        if text:
            if self.datastore:
                self._telegram_id = self.datastore.telegram_id
                self._proxy = self.datastore.proxy
                self._token = self.datastore.token_name
                text += f"\nChannel: {self.datastore.channel}"
            if self._telegram_id:
                text += f"\nTelegram_ID: {self._telegram_id}"
            if self._token:
                text += f"\nToken: {self._token}"
            if self._proxy:
                text += f"\nProxy [{self._proxy}]"
            if users and self._telegram_id:
                await self.send_message_to_user(text=text, telegram_id=self._telegram_id)
            if admins:
                await self.send_report_to_admins(text)
        error_message: str = (
            f"\n[Telegram_id: {self._telegram_id}"
            f"\tToken: {self._token}"
            f"\tProxy: {self._proxy}"
            f"\tError status: {self._status}"
            f"\n\tError data: {self._answer_data}]"
        )
        logger.error(error_message)

    @classmethod
    @logger.catch
    async def send_message_to_user(cls, text: str, telegram_id: str, keyboard=None) -> None:
        """Отправляет сообщение пользователю в телеграм"""

        params: dict = {
            "chat_id": telegram_id,
            "text": text
        }
        if keyboard:
            params.update(reply_markup=keyboard)
        try:
            await bot.send_message(**params)
        except aiogram.utils.exceptions.ChatNotFound:
            logger.error(f"Chat {telegram_id} not found")
        except aiogram.utils.exceptions.BotBlocked as err:
            logger.error(f"Пользователь {telegram_id} заблокировал бота {err}")
        except aiogram.utils.exceptions.CantInitiateConversation as err:
            logger.error(f"Не смог отправить сообщение пользователю {telegram_id}. {err}")
        logger.warning(f"Send_message_to_user: {telegram_id}: {text}")

    @classmethod
    @logger.catch
    async def send_report_to_admins(cls, text: str) -> None:
        """Отправляет сообщение в телеграме всем администраторам из списка"""

        text = f'[Рассылка][Superusers]: {text}'
        for admin_id in admins_list:
            await cls.send_message_to_user(text=text, telegram_id=admin_id)
