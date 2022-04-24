import datetime
import json
from datetime import timedelta
from json import JSONDecodeError
from typing import List, Tuple, Optional

import utils
from classes.db_interface import DBI
from classes.errors_sender import ErrorsSender
from classes.redis_interface import RedisDB
from classes.request_classes import ChannelData
from classes.token_datastorage import TokenData
from config import logger, DEBUG


class MessageReceiver(ChannelData):
    """Выбирает токен для отправки сообщения и вызывает метод вызова сообщения,
    проверяет его ответ, и, если есть свободные токены - повторяет процесс.
    При ошибке возвращает ее в телеграм"""

    @logger.catch
    async def __get_all_messages(self) -> List[dict]:
        """Отправляет GET запрос к АПИ, возвращает полученные данные"""

        self.proxy: str = self._datastore.proxy
        self.token: str = self._datastore.token

        answer: dict = await self._send()
        status: int = answer.get("status")
        if not status:
            logger.error(f"get_data_from_channel error: ")
        elif status == 200:
            try:
                return json.loads(answer.get("data"))
            except JSONDecodeError as err:
                logger.error("F: get_data_from_channel: JSON ERROR:", err)
        elif status == 401:
            await ErrorsSender.send_message_check_token(
                status=status, telegram_id=self._datastore.telegram_id, admins=False,
                token=self._datastore.token)
            await DBI.delete_token(token=self.token)
        return []

    @logger.catch
    async def get_message(self) -> Optional['TokenData']:
        """Получает данные из АПИ, выбирает случайное сообщение и возвращает ID сообщения
        и само сообщение"""

        # TODO сделать список в редис, куда складывать айдишники всех реплаев, на которые ответили
        # TODO Вынести работу с отправкой запросов в отдельный класс и написать обработку ошибок там
        # TODO Сделать флаг автоответа (если флаг стоит - то отвечает бот Давинчи, иначе -
        #  отправлять в телеграм юзеру
        # TODO выделить реплаи и работу с ними в отдельный класс

        user_message, message_id = await self.__get_user_message_from_redis()

        discord_messages: List[dict] = await self.__get_all_messages()
        logger.debug(f"Discord messages: {discord_messages}")
        if not discord_messages:
            return
        lms_id_and_replies: Tuple[int, List[
            dict]] = await self.__get_replies_and_message_id(data=discord_messages)
        self._datastore.current_message_id = lms_id_and_replies[0]
        self._datastore.replies = lms_id_and_replies[1]

        if message_id:
            self._datastore.current_message_id = message_id
        self._datastore.text_to_send = user_message if user_message else ''
        return self._datastore

    @logger.catch
    async def __get_user_message_from_redis(self) -> Tuple[str, int]:
        """Возвращает данные из Редиса"""

        answer: str = ''
        message_id = 0
        redis_data: List[dict] = await RedisDB(redis_key=self._datastore.my_discord_id).load()
        if not redis_data:
            return answer, message_id

        for elem in redis_data:
            # if not isinstance(elem, dict):
            #     continue
            answered = elem.get("answered", False)
            if not answered:
                answer = elem.get("answer_text", '')
                message_id = elem.get("message_id", 0)
                elem.update({"answered": True})
                await RedisDB(redis_key=self._datastore.my_discord_id).save(data=redis_data)
                break

        return answer, message_id

    @staticmethod
    @logger.catch
    def __get_delta_seconds(elem: dict) -> int:
        """Возвращает время, в пределах которого надо найти сообщения которое в секундах"""

        message_time: 'datetime' = elem.get("timestamp")
        mes_time: 'datetime' = datetime.datetime.fromisoformat(message_time).replace(tzinfo=None)
        delta: 'timedelta' = datetime.datetime.utcnow().replace(tzinfo=None) - mes_time

        return delta.seconds

    @logger.catch
    async def __get_my_replies(self, data: List[dict]) -> List[dict]:
        """Возвращает список всех упоминаний и реплаев наших токенов в сообщениях за последнее время"""

        return [
            elem
            for elem in data
            if (
                    elem.get("mentions")
                    and elem.get("mentions")[0].get("id", '') in self._datastore.all_tokens_ids
                    and elem.get("id") != self._datastore.mate_id
            )
        ]

    @logger.catch
    async def __get_last_messages(self, data: List[dict]) -> List[dict]:
        """Возвращает список всех сообщений за последнее время"""

        return list(
            filter(
                lambda x: self.__get_delta_seconds(x) < self._datastore.last_message_time,
                data
            )
        )

    @logger.catch
    async def __get_filtered_replies(self, data: List[dict]) -> List[dict]:
        """"""
        return [
            {
                "token": self._datastore.token,
                "author": elem.get("author", {}).get("username", ''),
                "text": elem.get("content", '[no content]'),
                "message_id": elem.get("id", ''),
                "to_message": elem.get("referenced_message", {}).get("content"),
                "to_user": elem.get("referenced_message", {}).get("author", {}).get("username"),
                "target_id": elem.get("mentions", [{"id": 0}][0].get("id", 0))
            }
            for elem in data
        ]

    @logger.catch
    async def __get_last_message_id_from_last_messages(self, data: List[dict]) -> int:
        """"""

        messages: List[dict] = [
            elem
            for elem in data
            if self._datastore.mate_id == str(elem["author"]["id"])
        ]
        return await self.__get_last_message_id(messages)

    # @logger.catch
    # async def __add_redis_replies(self, data: List[str]) -> None:
    #     """Adds data from list to Redis using discord id as key"""
    #
    #     if not data:
    #         return
    #     redis_key: str = f"{self._datastore.my_discord_id}"
    #     total_replies: List[str] = await RedisDB(redis_key).load()
    #     total_replies.extend(data)
    #     if DEBUG:
    #         utils.save_data_to_json(data=total_replies, file_name="updated_replies_list.json")
    #
    #     await RedisDB(redis_key).save(data=total_replies)

    @logger.catch
    async def __get_replies_and_message_id(self, data: List[dict]) -> Tuple[int, List[dict]]:
        """Сохраняет реплаи и последнее сообщение в datastore"""

        last_messages: List[dict] = await self.__get_last_messages(data)
        all_replies: List[dict] = await self.__get_my_replies(last_messages)
        new_replies: List[dict] = await self.__get_filtered_replies(all_replies)
        replies: List[dict] = await self.__save_replies_to_redis(new_replies)

        # replies_ids: List[str] = [elem.get("message_id") for elem in new_replies]
        # await self.__add_redis_replies(replies_ids)

        last_message_id: int = await self.__get_last_message_id_from_last_messages(last_messages)

        if DEBUG:
            utils.save_data_to_json(data=last_messages, file_name="last_messages.json")
            utils.save_data_to_json(data=all_replies, file_name="all_replies.json")
            utils.save_data_to_json(data=new_replies, file_name="new_replies.json", key='a')
            utils.save_data_to_json(data=[last_message_id], file_name="last_message_id.json")

        return last_message_id, replies

    @logger.catch
    async def __get_last_message_id(self, data: list) -> int:
        return int(max(data, key=lambda x: x.get("timestamp"))["id"]) if data else 0

    @logger.catch
    async def __save_replies_to_redis(self, new_replies: List[dict]) -> List[dict]:
        """Возвращает разницу между старыми и новыми данными в редисе,
        записывает полные данные в редис"""

        if not new_replies:
            return []
        total_replies: List[dict] = await RedisDB(redis_key=self._datastore.my_discord_id).load()
        old_messages: List[str] = list(map(lambda x: x.get("message_id"), total_replies))
        result: List[dict] = list(filter(lambda x: x.get("message_id") not in old_messages, new_replies))
        total_replies.extend(result)
        await RedisDB(redis_key=self._datastore.my_discord_id).save(data=total_replies)

        return result

    # @logger.catch
    # def __get_replies_for_my_tokens(self, elem: dict) -> dict:
    #     """Возвращает реплаи не из нашего села."""
    #
    #     utils.save_data_to_json(data=elem, file_name='elem.json')
    #
    #     result = {}
    #     ref_messages: dict = elem.get("referenced_message", {})
    #     if not ref_messages:
    #         return result
    #     ref_messages_author: dict = ref_messages.get("author", {})
    #     if not ref_messages_author:
    #         return result
    #     reply_for_author_id: str = ref_messages_author.get("id", '')
    #     mentions: tuple = tuple(
    #         filter(
    #             lambda x: str(x.get("id", '')) in self._datastore.all_tokens_ids,
    #             elem.get("mentions", [])
    #         )
    #     )
    #     author: str = elem.get("author", {}).get("username", '')
    #     author_id: str = elem.get("author", {}).get("id", '')
    #     message_for_me: bool = reply_for_author_id in self._datastore.all_tokens_ids
    #     if any(mentions) or message_for_me:
    #         all_discord_tokens: List[str] = self._datastore.all_tokens_ids
    #         if author_id not in all_discord_tokens:
    #             result.update({
    #                 "token": self._datastore.token,
    #                 "author": author,
    #                 "text": elem.get("content", ''),
    #                 "message_id": elem.get("id", ''),
    #                 "to_message": ref_messages.get("content"),
    #                 "to_user": ref_messages.get("author", {}).get("username")
    #             })
    #
    #     return result
