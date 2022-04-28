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
    async def send_message_to_discord(self) -> bool:
        """Отправляет данные в канал дискорда, возвращает результат отправки."""

        if self._datastore.data_for_send:
            return await self.__send_data()

    async def _typing(self) -> None:
        """Имитирует "Пользователь печатает" в чате дискорда."""

        self.url = f'https://discord.com/api/v9/channels/{self._datastore.channel}/typing'
        answer: dict = await self._send_request()
        if answer.get("status") not in range(200, 205):
            logger.warning(f"Typing ERROR: {answer}")
        await asyncio.sleep(2)

    async def __send_data(self) -> bool:
        """
        Sends data to discord channel
        :return:
        """
        self.token = self._datastore.token
        self.proxy = self._datastore.proxy
        self._data_for_send = self._datastore.data_for_send

        await self._typing()
        await self._typing()
        self.url = DISCORD_BASE_URL + f'{self._datastore.channel}/messages?'

        # logger.debug("MessageSender.__send_data::"
        #              f"\n\tToken: {self.token}"
        #              f"\n\tProxy:{self.proxy}"
        #              f"\n\tChannel: {self._datastore.channel}"
        #              f"\n\tData for send: {self._data_for_send}")

        answer: dict = await self._send_request()
        if answer.get("status") == 200:
            return True
        self._update_err_params(answer=answer, datastore=self._datastore)
        await ErrorsSender(**self._error_params).handle_errors()


