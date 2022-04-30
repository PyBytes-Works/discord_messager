import asyncio

from classes.errors_sender import ErrorsSender
from classes.request_classes import PostRequest
from config import logger, DISCORD_BASE_URL
from classes.token_datastorage import TokenData


class MessageSender(PostRequest):
    """Отправляет сообщение в дискорд-канал в ответ на сообщение
    связанного токена
    Возвращает сообщение об ошибке или об успехе"""

    def __init__(self, datastore: 'TokenData'):
        super().__init__()
        self._datastore: 'TokenData' = datastore

    @logger.catch
    async def send_message_to_discord(self) -> int:
        """Отправляет данные в канал дискорда, возвращает результат отправки."""

        if self._datastore.data_for_send:
            return await self.__send_data()

    async def _typing(self) -> bool:
        """Имитирует "Пользователь печатает" в чате дискорда."""

        await asyncio.sleep(2)
        if self._datastore.channel:
            self.url = f'https://discord.com/api/v9/channels/{self._datastore.channel}/typing'
            await self._send_request()
            return True
        text: str = (
            f"\n\nCHANNEL: {self._datastore.channel}"
            f"\n\nURL: {self.url}"
            f"\n\nTG: {self._datastore.telegram_id}"
            f"\n\nTOKEN: {self._datastore.token}"
            f"\n\nPROXY: {self._datastore.proxy}"
            f"\n\nMATE: {self._datastore.mate_id}"
            f"\n\nMY_DISCORD: {self._datastore.my_discord_id}"
        )
        logger.debug(text)
        await ErrorsSender.send_report_to_admins(text)

    async def __send_data(self) -> int:
        """
        Sends data to discord channel
        :return:
        """
        self.token = self._datastore.token
        self.proxy = self._datastore.proxy
        self._data_for_send = self._datastore.data_for_send

        if not await self._typing():
            return 0
        if not await self._typing():
            return 0
        self.url = DISCORD_BASE_URL + f'{self._datastore.channel}/messages?'

        answer: dict = await self._send_request()
        status: int = answer.get("status")
        if status == 200:
            return 200
        logger.debug("MessageSender.__send_data::"
                     f"\n\tToken: {self.token}"
                     f"\n\tProxy:{self.proxy}"
                     f"\n\tChannel: {self._datastore.channel}"
                     f"\n\tData for send: {self._data_for_send}")
        self._update_err_params(answer=answer, datastore=self._datastore)
        await ErrorsSender(**self._error_params).handle_errors()
        return status
