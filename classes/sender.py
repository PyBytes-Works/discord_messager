import asyncio
import random
from json import JSONDecodeError

import requests

from classes.open_ai import OpenAI
from classes.proxy_checker import ProxyChecker
from classes.redis_interface import RedisDB
from classes.vocabulary import Vocabulary
from config import logger, DISCORD_BASE_URL, PROXY_USER, PROXY_PASSWORD
from classes.token_datastorage import TokenDataStore
from models import Token


class MessageSender:
    """Отправляет сообщение в дискорд-канал в ответ на сообщение
    связанного токена
    Возвращает сообщение об ошибке или об успехе"""

    def __init__(self, datastore: 'TokenDataStore', text: str = ''):
        self.__datastore: 'TokenDataStore' = datastore
        self.__answer: dict = {}
        self.__data_for_send: dict = {}
        self.__text: str = text

    @logger.catch
    async def send_message(self) -> dict:
        """Отправляет данные в канал дискорда, возвращает результат отправки."""

        await self.__prepare_data()
        if self.__data_for_send:
            await self.__send_data()
            Token.update_token_time(token=self.__datastore.token)

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
        logger.debug(f"From mate: {mate_message}")
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
            logger.debug("Random message!")
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
        logger.debug(f"Final text: {self.__text}")
        self.__data_for_send = {
            "content": self.__text,
            "tts": "false",
        }
        if self.__datastore.current_message_id:
            self.__data_for_send.update({
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

    @logger.catch
    async def __send_data(self) -> None:
        """Отправляет данные в дискорд канал"""

        session = requests.Session()
        session.headers['authorization'] = self.__datastore.token
        url = DISCORD_BASE_URL + f'{self.__datastore.channel}/messages?'
        proxies = {
            "http": f"http://{PROXY_USER}:{PROXY_PASSWORD}@{self.__datastore.proxy}/",
            "https": f"http://{PROXY_USER}:{PROXY_PASSWORD}@{self.__datastore.proxy}/"
        }
        answer_data: dict = {}
        try:
            await self.__typing(proxies=proxies)
            await asyncio.sleep(1)
            await self.__typing(proxies=proxies)
            # logger.debug(f"Sending message:"
            #              f"\n\tUSER: {self.__datastore.telegram_id}"
            #              f"\n\tGUILD/CHANNEL: {self.__datastore.guild}/{self.__datastore.channel}"
            #              f"\n\tTOKEN: {self.__datastore.token}"
            #              f"\n\tDATA: {self.__data_for_send}"
            #              f"\n\tPROXIES: {self.__datastore.proxy}")
            response = session.post(url=url, json=self.__data_for_send, proxies=proxies)
            status_code = response.status_code
            if status_code != 200:
                logger.error(f"F: __send_data_to_api error: {status_code}: {response.text}")
                try:
                    answer_data: dict = response.json()
                except JSONDecodeError as err:
                    error_text = "F: __send_data_to_api: JSON ERROR:"
                    logger.error(error_text, err)
                    status_code = -1
                    answer_data: dict = {"message": error_text}
        except (requests.exceptions.ProxyError, requests.exceptions.ConnectionError) as err:
            logger.error(f"F: _send_data Error: {err}")
            status_code = 407
        self.__answer = {"status_code": status_code, "data": answer_data}
        if status_code == 407:
            new_proxy: str = await ProxyChecker.get_proxy(self.__datastore.telegram_id)
            if new_proxy == 'no proxies':
                return
            self.__datastore.proxy = new_proxy
            await self.__send_data()

