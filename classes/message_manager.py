import datetime
import random
from datetime import timedelta
from typing import List

from classes.errors_reporter import ErrorsReporter
from classes.open_ai import OpenAI
from classes.redis_interface import RedisDB
from classes.replies import RepliesManager
from classes.request_classes import ChannelData
from classes.token_datastorage import TokenData
from classes.vocabulary import Vocabulary
from config import logger


class MessageManager(ChannelData):
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

        self.datastore.for_reply = []
        self.datastore.current_message_id = 0
        self.datastore.text_to_send = ''
        all_messages: List[dict] = await self.__get_all_discord_messages()
        self._last_messages: List[dict] = await self.__get_last_messages(all_messages)
        if not await self.__get_message_id_and_text_for_send_answer():
            self.datastore.current_message_id = await self.__get_message_id_from_last_messages()
            self.datastore.text_to_send = await self._get_message_text()
        await self.__update_datastore_replies()
        await self.__get_data_for_send()

    @logger.catch
    async def __get_all_discord_messages(self) -> List[dict]:

        self.proxy: str = self.datastore.proxy
        self.token: str = self.datastore.token
        if not self.datastore.channel:
            return []
        answer: dict = await self._send_request()
        if answer and answer.get("status") == 200:
            return answer.get("answer_data")
        return []

    @logger.catch
    async def _get_message_text(self) -> str:
        """Return text for sending to discord. If 'mate' message exists - send it to OpenAi
        and returns result else return text from vocabulary"""

        mate_message: str = await self.__get_mate_message()
        if mate_message:
            openai_text: str = await self.__get_text_from_openai(mate_message)
            if openai_text:
                return openai_text
        if self._ten_from_hundred():
            logger.debug("Random message! You are lucky!!!")
            self.datastore.current_message_id = 0
        return await self.__get_text_from_vocabulary()

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
                    and elem.get("mentions")[0].get("id", '') in self.datastore.all_tokens_ids
                    and elem.get("id") != self.datastore.mate_id
            )
        ]

    @logger.catch
    async def __get_last_messages(self, all_messages: List[dict]) -> List[dict]:
        """Возвращает список всех сообщений за последнее время"""

        if not all_messages:
            return []
        return list(
            filter(
                lambda x: self.__get_delta_seconds(x) < self.datastore.last_message_time,
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
                or self.datastore.token
        )

    @logger.catch
    async def __get_filtered_replies(self, data: List[dict]) -> List[dict]:
        """"""

        return [
            {
                "token": self.datastore.token_name,
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
    async def __get_message_id_from_last_messages(self) -> int:
        """Returns message id from random message where author is mate"""

        if not self._last_messages:
            return 0
        mate_messages: List[dict] = [
            elem
            for elem in self._last_messages
            if self.datastore.mate_id == str(elem["author"]["id"])
        ]
        return await self.__get_random_message_id(mate_messages)

    @logger.catch
    async def __get_random_message_id(self, data: list) -> int:
        if not data:
            return 0
        random_elem: dict = random.choice(data)
        return random_elem.get("id", 0)

    @logger.catch
    async def __update_datastore_replies(self) -> None:
        """Сохраняет реплаи и последнее сообщение в datastore"""

        if not self._last_messages:
            return
        all_replies: List[dict] = await self.__get_my_replies()
        new_replies: List[dict] = await self.__get_filtered_replies(all_replies)
        await self.__update_replies(new_replies)

    @logger.catch
    async def __update_replies(self, new_replies: List[dict]) -> None:
        """Возвращает разницу между старыми и новыми данными в редисе,
        записывает полные данные в редис"""

        await RepliesManager(self.datastore.telegram_id).update_new_replies(new_replies)

    @logger.catch
    async def __get_message_id_and_text_for_send_answer(self) -> int:

        """Update datastore message id and answer text from answered replies from Redis

        Returns length of replies list"""

        replies: 'RepliesManager' = RepliesManager(redis_key=self.datastore.telegram_id)
        my_answered: List[dict] = await replies.get_not_answered_with_text(self.datastore.my_discord_id)
        if my_answered:
            current_reply: dict = my_answered.pop()
            self.datastore.text_to_send = current_reply.get("answer_text")
            message_id: str = current_reply.get("message_id")
            self.datastore.current_message_id = message_id
            await replies.update_answered(message_id)

        return self.datastore.current_message_id

    @logger.catch
    async def __get_text_from_vocabulary(self) -> str:
        text: str = Vocabulary.get_message()
        if not text:
            await ErrorsReporter.send_report_to_admins(text="Ошибка словаря фраз.")
            return ''
        await RedisDB(redis_key=self.datastore.mate_id).save(data=[
            text], timeout_sec=self.datastore.delay + 300)
        return text

    @logger.catch
    async def __get_text_from_openai(self, mate_message: str) -> str:

        openai_answer: str = await self.__get_openai_answer(mate_message)
        logger.debug(f"\n\t\tFirst OpenAI answer: {openai_answer}\n")
        if openai_answer:
            if self._fifty_fifty():
                logger.debug("50 / 50 You got it!!!")
                self.datastore.current_message_id = 0
            return openai_answer
        random_message: str = await self.__get_random_message_from_last_messages()
        logger.debug(f"\n\t\tRandom OpenAI answer: {random_message}\n")

        return random_message

    @logger.catch
    async def __get_random_message_from_last_messages(self) -> str:
        message_data: dict = random.choice(self._last_messages)
        text: str = message_data.get("content", '')
        logger.debug(f"Random message from last messages: {text}")
        result: str = await self.__get_openai_answer(text)
        if result != text:
            self.datastore.current_message_id = int(message_data.get("id", 0))
            return result
        return ''

    @logger.catch
    async def __get_mate_message(self) -> str:
        mate_message: List[str] = await RedisDB(redis_key=self.datastore.my_discord_id).load()
        if mate_message:
            await RedisDB(
                redis_key=self.datastore.my_discord_id).delete(mate_id=self.datastore.mate_id)
            return mate_message[0]
        return ''

    @staticmethod
    @logger.catch
    async def __get_openai_answer(text: str) -> str:
        if not text:
            return ''
        return OpenAI().get_answer(text.strip())

    @logger.catch
    async def __get_data_for_send(self) -> None:
        """Сохраняет в datastore данные для отправки в дискорд"""

        if not self.datastore.text_to_send:
            logger.warning("\n\t\tMessage_receiver.__prepare_data: no text for sending.\n")
            return
        self.datastore.data_for_send = {
            "content": self.datastore.text_to_send,
            "tts": "false"
        }
        if self.datastore.current_message_id:
            params: dict = {
                "message_reference":
                    {
                        "guild_id": self.datastore.guild,
                        "channel_id": self.datastore.channel,
                        "message_id": self.datastore.current_message_id
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
            self.datastore.data_for_send.update(**params)

    @staticmethod
    @logger.catch
    def _ten_from_hundred() -> bool:
        return random.randint(1, 100) <= 10

    @staticmethod
    @logger.catch
    def _fifty_fifty() -> bool:
        return random.randint(1, 100) <= 50
