import datetime
from datetime import timedelta
from typing import List, Tuple

import utils
from classes.errors_sender import ErrorsSender
from classes.redis_interface import RedisDB
from classes.request_classes import ChannelData
from config import logger, DEBUG, SAVING


class MessageReceiver(ChannelData):
    """Получает сообщения из дискорда и формирует данные для ответа
    и реплаев"""

    @logger.catch
    async def get_message(self) -> None:
        """Получает данные из АПИ, выбирает случайное сообщение и
        возвращает ID сообщения
        и само сообщение"""

        user_message, message_id = await self.__get_user_message_from_redis()

        discord_messages: List[dict] = await self.__get_discord_messages()
        await self.__get_replies_and_message_id(discord_messages)
        if message_id:
            self._datastore.current_message_id = message_id
        self._datastore.text_to_send = user_message if user_message else ''

    @logger.catch
    async def __get_discord_messages(self) -> List[dict]:

        self.proxy: str = self._datastore.proxy
        self.token: str = self._datastore.token

        answer: dict = await self._send_request()
        self._error_params.update(answer=answer, telegram_id=self._datastore.telegram_id)
        logger.debug("MessageReceiver.__get_discord_messages call error handling:"
                     f"\nParams: {self._error_params}")
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
    async def __get_my_replies(self, data: List[dict]) -> List[dict]:
        """Возвращает список всех упоминаний и реплаев наших токенов в
        сообщениях за последнее время"""

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
    async def __get_target_id(self, elem: dict) -> str:
        return (
                elem.get("referenced_message", {}).get("author", {}).get("id")
                or elem.get("mentions", [{"id": '[no id]'}])[0].get("id")
        )

    @logger.catch
    async def __get_target_username(self, elem: dict) -> str:
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
                "to_user": await self.__get_target_username(elem),
                "target_id": await self.__get_target_id(elem)
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

    @logger.catch
    async def __get_replies_and_message_id(self, data: List[dict]) -> None:
        """Сохраняет реплаи и последнее сообщение в datastore"""

        if not data:
            self._datastore.replies = []
            self._datastore.current_message_id = 0
            return
        last_messages: List[dict] = await self.__get_last_messages(data)
        all_replies: List[dict] = await self.__get_my_replies(last_messages)
        new_replies: List[dict] = await self.__get_filtered_replies(all_replies)
        self._datastore.replies = await self.__save_replies_to_redis(new_replies)
        self._datastore.current_message_id = await self.__get_last_message_id_from_last_messages(last_messages)
        # logger.error(f"NEW REPLIES: {self._datastore.replies}")
        # logger.error(f"MESSAGE ID: {self._datastore.current_message_id}")
        utils.save_data_to_json(data=last_messages, file_name="last_messages.json", key='a')

        if DEBUG and SAVING:
            utils.save_data_to_json(data=last_messages, file_name="last_messages.json")
            utils.save_data_to_json(data=all_replies, file_name="all_replies.json")
            utils.save_data_to_json(data=new_replies, file_name="new_replies.json", key='a')
            utils.save_data_to_json(data=[self._datastore.current_message_id], file_name="last_message_id.json")

    @logger.catch
    async def __get_last_message_id(self, data: list) -> int:
        return int(max(data, key=lambda x: x.get("timestamp"))["id"]) if data else 0

    @logger.catch
    async def __save_replies_to_redis(self, new_replies: List[dict]) -> List[dict]:
        """Возвращает разницу между старыми и новыми данными в редисе,
        записывает полные данные в редис"""

        if not new_replies:
            return []
        total_replies: List[dict] = await RedisDB(redis_key=self._datastore.telegram_id).load()
        old_messages: List[str] = list(map(lambda x: x.get("message_id"), total_replies))
        result: List[
            dict] = list(filter(lambda x: x.get("message_id") not in old_messages, new_replies))
        total_replies.extend(result)
        await RedisDB(redis_key=self._datastore.telegram_id).save(data=total_replies)

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
            answered: bool = elem.get("answered", False)
            for_me: bool = int(elem.get("target_id")) == int(self._datastore.my_discord_id)
            if for_me and not answered:
                answer: str = elem.get("answer_text", '')
                message_id: int = elem.get("message_id", 0)
                elem.update({"answered": True})
                await RedisDB(redis_key=self._datastore.telegram_id).save(data=redis_data)
                break

        return answer, message_id
