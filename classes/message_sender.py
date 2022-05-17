import asyncio

from classes.request_classes import PostRequest, DISCORD_BASE_URL
from config import logger
from classes.token_datastorage import TokenData


class MessageSender(PostRequest):
    """Отправляет сообщение в дискорд-канал в ответ на сообщение
    связанного токена
    Возвращает сообщение об ошибке или об успехе"""

    def __init__(self, datastore: 'TokenData'):
        super().__init__()
        self.datastore: 'TokenData' = datastore
        self.channel: int = 0

    @logger.catch
    async def send_message_to_discord(self) -> dict:
        """Отправляет данные в канал дискорда, возвращает результат отправки."""

        if self.datastore.data_for_send:
            return await self.__send_data()
        return {}

    async def _typing(self) -> None:
        """Имитирует "Пользователь печатает" в чате дискорда."""

        self.url = f'https://discord.com/api/v9/channels/{self.channel}/typing'
        await self._send_request()

    async def __send_data(self) -> dict:
        """
        Sends data to discord channel
        :return:
        """

        await asyncio.sleep(1)
        self.token = self.datastore.token
        self.proxy = self.datastore.proxy
        self.channel = self.datastore.channel
        self._data_for_send = self.datastore.data_for_send

        await self._typing()
        await asyncio.sleep(2)
        await self._typing()

        self.url = DISCORD_BASE_URL + f'{self.channel}/messages?'
        return await self._send_request()
