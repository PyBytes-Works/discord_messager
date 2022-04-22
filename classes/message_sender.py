import asyncio
import random

from classes.open_ai import OpenAI
from classes.redis_interface import RedisDB
from classes.request_sender import SendMessageToChannel
from classes.vocabulary import Vocabulary
from config import logger, DEFAULT_PROXY
from classes.token_datastorage import TokenDataStore


class MessageSender(SendMessageToChannel):
    """Отправляет сообщение в дискорд-канал в ответ на сообщение
    связанного токена
    Возвращает сообщение об ошибке или об успехе"""

    def __init__(self, datastore: 'TokenDataStore'):
        super().__init__(datastore)
        self.__text: str = ''

    @logger.catch
    async def send_message(self, text: str) -> dict:
        """Отправляет данные в канал дискорда, возвращает результат отправки."""

        self.__text = text
        await self.__prepare_data()
        if self._datastore.data_for_send:
            return await self.send_data()

        return {}

    @logger.catch
    async def __get_text_from_vocabulary(self) -> str:
        # text: str = Vocabulary.get_message()
        text = "hello world"
        if text == "Vocabulary error":
            self.__answer = {"status_code": -2, "data": {"message": text}}
            return ''
        await RedisDB(redis_key=self._datastore.mate_id).save(data=[text], timeout_sec=self._datastore.delay + 300)
        return text

    @logger.catch
    async def __prepare_message_text(self) -> None:
        mate_message: list = await RedisDB(redis_key=self._datastore.my_discord_id).load()
        if mate_message:
            self.__text: str = OpenAI().get_answer(mate_message[0].strip())
            await RedisDB(redis_key=self._datastore.my_discord_id).delete(mate_id=self._datastore.mate_id)
        if not self.__text:
            self.__text: str = await self.__get_text_from_vocabulary()

    @logger.catch
    def __roll_the_dice(self) -> bool:
        return random.randint(1, 100) <= 10

    async def __get_text(self) -> None:
        if self.__text:
            return
        if self.__roll_the_dice():
            logger.debug("Random message! You are lucky!!!")
            self._datastore.current_message_id = 0
            self.__text = await self.__get_text_from_vocabulary()
            return
        await self.__prepare_message_text()

    @logger.catch
    async def __prepare_data(self) -> None:
        """Возвращает сформированные данные для отправки в дискорд"""

        await self.__get_text()
        if not self.__text:
            return
        self._datastore.data_for_send = {
            "content": self.__text,
            "tts": "false",
        }
        if self._datastore.current_message_id:
            self._datastore.data_for_send.update({
                "message_reference":
                    {
                        "guild_id": self._datastore.guild,
                        "channel_id": self._datastore.channel,
                        "message_id": self._datastore.current_message_id
                    },
                "allowed_mentions":
                    {
                        "parse": [
                            "users",
                            "roles",
                            "everyone"
                        ],
                        "replied_user": "false"
                    }
            })
