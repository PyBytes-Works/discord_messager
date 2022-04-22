import asyncio
import datetime
import json
import random
from json import JSONDecodeError
from typing import List, Tuple, Union

from classes.message_sender import MessageSender
from classes.redis_interface import RedisDB
from classes.request_sender import GetChannelData
from config import logger, DEBUG, DEFAULT_PROXY
from classes.token_datastorage import TokenDataStore


class MessageReceiver(GetChannelData):

    """Выбирает токен для отправки сообщения и вызывает метод вызова сообщения,
    проверяет его ответ, и, если есть свободные токены - повторяет процесс.
    При ошибке возвращает ее в телеграм"""

    def __init__(self, datastore: 'TokenDataStore'):
        super().__init__()
        self._datastore: 'TokenDataStore' = datastore
        self.limit: int = 100

    @logger.catch
    async def get_messages(self) -> Union[List[dict], dict]:
        """Отправляет GET запрос к АПИ, возвращает полученные данные"""

        self.proxy: str = self._datastore.proxy
        self.token: str = self._datastore.token
        self.channel: Union[str, int] = self._datastore.channel

        answer: dict = await self._send()
        status: int = answer.get("status")
        if not status:
            logger.error(f"get_data_from_channel error: ")
        elif status == 200:
            try:
                return json.loads(answer.get("data"))
            except JSONDecodeError as err:
                logger.error("F: get_data_from_channel: JSON ERROR:", err)

    @logger.catch
    async def get_message(self) -> dict:
        """Получает данные из АПИ, выбирает случайное сообщение и возвращает ID сообщения
        и само сообщение"""

        # TODO сделать список в редис, куда складывать айдишники всех реплаев, на которые ответили
        # TODO Вынести работу с отправкой запросов в отдельный класс и написать обработку ошибок там
        # TODO Сделать флаг автоответа (если флаг стоит - то отвечает бот Давинчи, иначе -
        #  отправлять в телеграм юзеру
        # TODO выделить реплаи и работу с ними в отдельный класс

        result = {"work": False}
        user_message, message_id = await self.__get_user_message_from_redis()

        filtered_data: dict = await self.__get_filtered_data()
        replies: List[dict] = filtered_data.get("replies", [])
        result.update({"replies": replies})

        if message_id:
            self._datastore.current_message_id = message_id
        elif filtered_data:
            self._datastore.current_message_id = filtered_data.get("last_message_id", 0)
        text_to_send: str = user_message if user_message else ''
        answer: dict = await MessageSender(datastore=self._datastore).send_message(text=text_to_send)
        if not answer:
            logger.error("F: get_message ERROR: NO ANSWER ERROR")
            result.update({"message": "ERROR"})
            return result
        elif answer.get("status") != 200:
            result.update({"answer": answer, "token": self._datastore.token})
            return result

        self._datastore.current_message_id = 0
        result.update({"work": True})
        if not DEBUG:
            timer: float = 7 + random.randint(0, 6)
            logger.info(f"Пауза между отправкой сообщений: {timer}")
            await asyncio.sleep(timer)

        return result

    @logger.catch
    async def __get_user_message_from_redis(self) -> Tuple[str, int]:
        """Возвращает данные из Редиса"""

        answer: str = ''
        message_id = 0
        redis_data: List[dict] = await RedisDB(redis_key=self._datastore.telegram_id).load()
        if not redis_data:
            return answer, message_id

        for elem in redis_data:
            if not isinstance(elem, dict):
                continue
            answered = elem.get("answered", False)
            if not answered:
                if elem.get("token") == self._datastore.token:
                    answer = elem.get("answer_text", '')
                    if answer:
                        message_id = elem.get("message_id", 0)
                        elem.update({"answered": True})
                        await RedisDB(redis_key=self._datastore.telegram_id).save(data=redis_data)
                        break

        return answer, message_id

    @logger.catch
    async def __get_filtered_data(self) -> dict:
        """Отправляет запрос к АПИ"""

        data: List[dict] = await self.get_messages()
        if not data:
            return {}
        result: dict = await self.__data_filter(data=data)

        return result

    @logger.catch
    async def __data_filter(self, data: List[dict]) -> dict:
        """Фильтрует полученные данные"""

        messages = []
        replies = []
        result = {}
        for elem in data:

            message_time: 'datetime' = elem.get("timestamp")
            mes_time = datetime.datetime.fromisoformat(message_time).replace(tzinfo=None)
            delta = datetime.datetime.utcnow().replace(tzinfo=None) - mes_time
            if delta.seconds < self._datastore.last_message_time:
                filtered_replies: dict = self.__get_replies_for_my_tokens(elem=elem)
                if filtered_replies:
                    replies.append(filtered_replies)
                is_author_mate: bool = str(self._datastore.mate_id) == str(elem["author"]["id"])
                my_message: bool = str(elem["author"]["id"]) == str(self._datastore.my_discord_id)
                if is_author_mate and not my_message:
                    spam: dict = {
                            "id": elem.get("id"),
                            "timestamp": message_time,
                        }
                    messages.append(spam)
        last_message_id: int = await self.__get_last_message_id(data=messages)
        result.update({"last_message_id": last_message_id})
        print("Replies before:", replies)
        replies: List[dict] = await self.__update_replies_to_redis(new_replies=replies)
        result.update({"replies": replies})
        print("Replies after:", replies)

        return result

    @logger.catch
    async def __get_last_message_id(self, data: list) -> int:
        if not data:
            return 0
        return int(max(data, key=lambda x: x.get("timestamp"))["id"])

    @logger.catch
    async def __update_replies_to_redis(self, new_replies: list) -> list:
        """Возвращает разницу между старыми и новыми данными в редисе,
        записывает полные данные в редис"""

        if not new_replies:
            return []
        total_replies: List[dict] = await RedisDB(redis_key=self._datastore.telegram_id).load()
        old_messages: list = list(map(lambda x: x.get("message_id"), total_replies))
        result: List[dict] = [
            elem
            for elem in new_replies
            if elem.get("message_id") not in old_messages
        ]

        total_replies.extend(result)
        await RedisDB(redis_key=self._datastore.telegram_id).save(data=total_replies)

        return result

    @logger.catch
    def __get_replies_for_my_tokens(self, elem: dict) -> dict:
        """Возвращает реплаи не из нашего села."""

        result = {}
        ref_messages: dict = elem.get("referenced_message", {})
        if not ref_messages:
            return result
        ref_messages_author: dict = ref_messages.get("author", {})
        if not ref_messages_author:
            return result
        reply_for_author_id: str = ref_messages_author.get("id", '')
        mentions: tuple = tuple(
            filter(
                lambda x: int(x.get("id", '')) == int(self._datastore.my_discord_id),
                elem.get("mentions", [])
            )
        )
        author: str = elem.get("author", {}).get("username", '')
        author_id: str = elem.get("author", {}).get("id", '')
        message_for_me: bool = reply_for_author_id == self._datastore.my_discord_id
        if any(mentions) or message_for_me:
            all_discord_tokens: List[str] = self._datastore.all_tokens_ids
            print(f"Author ID: {author_id}")
            print(f"IDS: {all_discord_tokens}")
            if author_id not in all_discord_tokens:
                result.update({
                    "token": self._datastore.token,
                    "author": author,
                    "text": elem.get("content", ''),
                    "message_id": elem.get("id", ''),
                    "to_message": ref_messages.get("content"),
                    "to_user": ref_messages.get("author", {}).get("username")
                })

        return result
