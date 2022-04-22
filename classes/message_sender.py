import asyncio
import random
from json import JSONDecodeError

import requests

from classes.open_ai import OpenAI
from classes.redis_interface import RedisDB
from classes.request_sender import SomeChecker
from classes.vocabulary import Vocabulary
from config import logger, DISCORD_BASE_URL, PROXY_USER, PROXY_PASSWORD
from classes.token_datastorage import TokenDataStore


class MessageSender:
    """Отправляет сообщение в дискорд-канал в ответ на сообщение
    связанного токена
    Возвращает сообщение об ошибке или об успехе"""

    def __init__(self, datastore: 'TokenDataStore', text: str = ''):
        self.__datastore: 'TokenDataStore' = datastore
        self.__answer: dict = {}
        self.__text: str = text

    @logger.catch
    async def send_message(self) -> dict:
        """Отправляет данные в канал дискорда, возвращает результат отправки."""

        await self.__prepare_data()
        if self.__datastore.data_for_send:
            await self._send()

        return self.__answer

    @logger.catch
    async def __get_text_from_vocabulary(self) -> str:
        text: str = Vocabulary.get_message()
        if text == "Vocabulary error":
            self.__answer = {"status_code": -2, "data": {"message": text}}
            return ''
        await RedisDB(redis_key=self.__datastore.mate_id).save(data=[text], timeout_sec=self.__datastore.delay + 300)
        return text

    @logger.catch
    async def __prepare_message_text(self) -> None:
        mate_message: list = await RedisDB(redis_key=self.__datastore.my_discord_id).load()
        if mate_message:
            self.__text: str = OpenAI().get_answer(mate_message[0].strip())
            await RedisDB(redis_key=self.__datastore.my_discord_id).delete(mate_id=self.__datastore.mate_id)
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
            self.__datastore.current_message_id = 0
            self.__text = await self.__get_text_from_vocabulary()
            return
        await self.__prepare_message_text()

    @logger.catch
    async def __prepare_data(self) -> None:
        """Возвращает сформированные данные для отправки в дискорд"""

        await self.__get_text()
        if not self.__text:
            return
        self.__datastore.data_for_send = {
            "content": self.__text,
            "tts": "false",
        }
        if self.__datastore.current_message_id:
            self.__datastore.data_for_send.update({
                "message_reference":
                    {
                        "guild_id": self.__datastore.guild,
                        "channel_id": self.__datastore.channel,
                        "message_id": self.__datastore.current_message_id
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

    @logger.catch
    async def __typing(self, proxies: dict) -> None:
        """Имитирует "Пользователь печатает" в чате дискорда."""

        response = requests.post(
            f'https://discord.com/api/v9/channels/{self.__datastore.channel}/typing',
            headers={
                "Authorization": self.__datastore.token,
                "Content-Length": "0"
            },
            proxies=proxies
        )
        if response.status_code != 204:
            logger.warning(f"Typing: {response.status_code}: {response.text}")
        await asyncio.sleep(2)


