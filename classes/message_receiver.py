import datetime
import random
from datetime import timedelta
from typing import List

import utils
from classes.errors_sender import ErrorsSender
from classes.open_ai import OpenAI
from classes.redis_interface import RedisDB
from classes.replies import RepliesManager
from classes.request_classes import ChannelData
from classes.token_datastorage import TokenData
from classes.vocabulary import Vocabulary
from config import logger, DEBUG, SAVING


class MessageReceiver(ChannelData):
    """Получает сообщения из дискорда и формирует данные для ответа
    и реплаев"""

    def __init__(self, datastore: 'TokenData'):
        super().__init__(datastore)
        self._last_messages: List[dict] = []

    @logger.catch
    async def get_message(self) -> None:
        """Получает данные из АПИ, выбирает случайное сообщение и
        возвращает ID сообщения
        и само сообщение"""

        self._datastore.for_reply = []
        self._datastore.current_message_id = 0
        self._datastore.text_to_send = ''
        all_messages: List[dict] = await self.__get_all_discord_messages()
        self._last_messages: List[dict] = await self.__get_last_messages(all_messages)
        if not await self.__update_datastore_message_id_and_answer_text_from_replies():
            self._datastore.current_message_id = await self.__get_last_message_id()
            self._datastore.text_to_send = await self.__get_message_text()
            logger.debug(f"\n\t\tTOTAL: self._datastore.text_to_send: {self._datastore.text_to_send}\n\n" )
        await self.__update_datastore_replies()
        await self.__get_data_for_send()

    @logger.catch
    async def __get_all_discord_messages(self) -> List[dict]:

        self.proxy: str = self._datastore.proxy
        self.token: str = self._datastore.token
        answer: dict = await self._send_request()
        self._error_params.update(answer=answer, telegram_id=self._datastore.telegram_id)
        result: dict = await ErrorsSender(**self._error_params).handle_errors()
        if result.get("status") == 200:
            return result.get("answer_data")
        return []

    @staticmethod
    @logger.catch
    def __get_delta_seconds(elem: dict) -> int:
        """Возвращает время, в пределах которого надо найти сообщения
        которое в секундах"""

        message_time: 'datetime' = elem.get("timestamp")
        mes_time: 'datetime' = datetime.datetime.fromisoformat(message_time).replace(tzinfo=None)
        delta: 'timedelta' = datetime.datetime.utcnow().replace(tzinfo=None) - mes_time

        return delta.seconds

    @logger.catch
    async def __get_my_replies(self) -> List[dict]:
        """Возвращает список всех упоминаний и реплаев наших токенов в
        сообщениях за последнее время"""

        return [
            elem
            for elem in self._last_messages
            if (
                    elem.get("mentions")
                    and elem.get("mentions")[0].get("id", '') in self._datastore.all_tokens_ids
                    and elem.get("id") != self._datastore.mate_id
            )
        ]

    @logger.catch
    async def __get_last_messages(self, all_messages: List[dict]) -> List[dict]:
        """Возвращает список всех сообщений за последнее время"""

        return list(
            filter(
                lambda x: self.__get_delta_seconds(x) < self._datastore.last_message_time,
                all_messages
            )
        )

    @logger.catch
    def __get_target_id(self, elem: dict) -> str:
        return (
                elem.get("referenced_message", {}).get("author", {}).get("id")
                or elem.get("mentions", [{"id": '[no id]'}])[0].get("id")
        )

    @logger.catch
    def __get_target_username(self, elem: dict) -> str:
        return (
                elem.get("referenced_message", {}).get("author", {}).get("username")
                or elem.get("mentions", [{"id": '[no id]'}])[0].get("username")
                or self._datastore.token
        )

    @logger.catch
    async def __get_filtered_replies(self, data: List[dict]) -> List[dict]:
        """"""
        if data and DEBUG and SAVING:
            utils.save_data_to_json(data, "replies_data.json", key='a')
        return [
            {
                "token": self._datastore.token_name,
                "author": elem.get("author", {}).get("username", 'no author'),
                "text": elem.get("content", '[no content]'),
                "message_id": elem.get("id", 0),
                "to_message": elem.get("referenced_message", {}).get("content", 'mention'),
                "to_user": self.__get_target_username(elem),
                "target_id": self.__get_target_id(elem)
            }
            for elem in data
        ]

    @logger.catch
    async def __get_last_message_id(self) -> int:
        """"""

        messages: List[dict] = [
            elem
            for elem in self._last_messages
            if self._datastore.mate_id == str(elem["author"]["id"])
        ]
        return await self.__get_last_message_id_from_messages(messages)

    @logger.catch
    async def __update_datastore_replies(self) -> None:
        """Сохраняет реплаи и последнее сообщение в datastore"""

        if not self._last_messages:
            return
        all_replies: List[dict] = await self.__get_my_replies()
        new_replies: List[dict] = await self.__get_filtered_replies(all_replies)
        self._datastore.for_reply = await self.__get_replies_for_answer(new_replies)

    @logger.catch
    async def __get_last_message_id_from_messages(self, data: list) -> int:
        return int(max(data, key=lambda x: x.get("timestamp"))["id"]) if data else 0

    @logger.catch
    async def __get_replies_for_answer(self, new_replies: List[dict]) -> List[dict]:
        """Возвращает разницу между старыми и новыми данными в редисе,
        записывает полные данные в редис"""

        return await RepliesManager(self._datastore.telegram_id).get_difference_and_update(new_replies)

    @logger.catch
    async def __update_datastore_message_id_and_answer_text_from_replies(self) -> int:

        """Update datastore message id and answer text from answered replies from Redis

        Returns length of replies list"""

        replies: 'RepliesManager' = RepliesManager(redis_key=self._datastore.telegram_id)
        my_answered: List[dict] = await replies.get_answered(self._datastore.my_discord_id)
        if my_answered:
            current_reply: dict = random.choice(my_answered)
            self._datastore.text_to_send = current_reply.get("answer_text")
            message_id: int = current_reply.get("message_id")
            self._datastore.current_message_id = message_id

        return len(my_answered)

    @logger.catch
    async def __get_text_from_vocabulary(self) -> str:
        text: str = Vocabulary.get_message()
        if not text:
            await ErrorsSender.send_report_to_admins(text="Ошибка словаря фраз.")
            return ''
        await RedisDB(redis_key=self._datastore.mate_id).save(data=[
            text], timeout_sec=self._datastore.delay + 300)
        return text

    @logger.catch
    async def __get_text_from_openai(self) -> str:
        result: str = ''
        mate_message: list = await RedisDB(redis_key=self._datastore.my_discord_id).load()
        logger.debug(f"Mate message: {mate_message}")
        if mate_message:
            await RedisDB(
                redis_key=self._datastore.my_discord_id).delete(mate_id=self._datastore.mate_id)
            text: str = OpenAI().get_answer(mate_message[0].strip())
            if not text:
                message_data: dict = random.choice(self._last_messages)
                text: str = message_data.get("content", '')
                logger.debug(f"Random message from last messages: {text}")
                if text:
                    result: str = OpenAI().get_answer(text.strip())
                    self._datastore.current_message_id = int(message_data.get("id", 0))
                    return result
            if self._fifty_fifty():
                logger.debug("50 / 50 You got it!!!")
                self._datastore.current_message_id = 0
        return result

    @logger.catch
    async def __get_message_text(self) -> str:
        openai_text: str = await self.__get_text_from_openai()
        if openai_text:
            return openai_text
        if self._ten_from_hundred():
            logger.debug("Random message! You are lucky!!!")
            self._datastore.current_message_id = 0
        text: str = await self.__get_text_from_vocabulary()

        return text

    @logger.catch
    async def __get_data_for_send(self) -> None:
        """Возвращает сформированные данные для отправки в дискорд"""

        if not self._datastore.text_to_send:
            logger.warning("\n\t\tMessage_receiver.__prepare_data: no text for sending.\n")
            return
        self._datastore.data_for_send = {
            "content": self._datastore.text_to_send,
            "tts": "false"
        }
        if self._datastore.current_message_id:
            params: dict = {
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
            }
            self._datastore.data_for_send.update(**params)

    @staticmethod
    @logger.catch
    def _ten_from_hundred() -> bool:
        return random.randint(1, 100) <= 10

    @staticmethod
    @logger.catch
    def _fifty_fifty() -> bool:
        return random.randint(1, 100) <= 50
