from typing import List

from classes.redis_interface import RedisDB
from config import logger


class ReplyData:

    """Reply dataclass"""

    def __init__(self, **kwargs):
        self.token: str = kwargs.get("token")
        self.author: str = kwargs.get("author", {}).get("username", 'no author')
        self.text: str = kwargs.get("content", '[no content]')
        self.message_id: str = str(kwargs.get("id", 0))
        self.to_message: int = kwargs.get("referenced_message", {}).get("content", 'mention')
        self.to_user: str = self.__get_target_username(kwargs)
        self.target_id: str = self.__get_target_id(kwargs)
        self.answer_text: str = ''
        self.showed: bool = False
        self.answered: bool = False

    @staticmethod
    def __get_target_id(elem: dict) -> str:
        return (
                elem.get("referenced_message", {}).get("author", {}).get("id")
                or elem.get("mentions", [{"id": '[no id]'}])[0].get("id")
        )

    @staticmethod
    def __get_target_username(elem: dict) -> str:
        return (
                elem.get("referenced_message", {}).get("author", {}).get("username")
                or elem.get("mentions", [{"id": '[no id]'}])[0].get("username")
        )

    def set_answered(self):
        self.answered = True

    def set_showed(self):
        self.showed = True

    def get_dict(self) -> dict:
        return self.__dict__

    def __str__(self) -> str:
        return f"{self.__dict__}"


class RepliesManager(RedisDB):

    """Класс для работы с реплаями - загрузка, сохранение, фильтрация"""

    def __init__(self, redis_key: str):
        super().__init__(redis_key)

    async def get_not_showed(self) -> List[ReplyData]:
        return [
            elem
            for elem in await self.load()
            if not elem.showed
        ]

    # @logger.catch
    # async def get_difference_and_update(self, new_replies: List[dict]) -> List[dict]:
    #     """Возвращает разницу между старыми и новыми данными в редисе,
    #     записывает полные данные в редис"""
    #
    #     if not new_replies:
    #         return []
    #     total_replies: List[dict] = await self.load()
    #     unanswered: List[dict] = await self._get_unanswered(total_replies)
    #     old_messages: List[str] = await self._get_old_replies_message_ids(unanswered)
    #     result: List[dict] = list(filter(
    #         lambda x: x.get("message_id") not in old_messages, new_replies))
    #     total_replies.extend(result)
    #     await self.save(data=total_replies)
    #
    #     return result

    @logger.catch
    async def update_new_replies(self, new_replies: List[ReplyData]) -> None:
        """Возвращает разницу между старыми и новыми данными в редисе,
        записывает полные данные в редис"""

        if not new_replies:
            return
        all_replies: List[ReplyData] = await self.load_replies()
        old_messages: List[str] = await self._get_old_replies_message_ids(all_replies)
        result: List[ReplyData] = list(filter(
            lambda x: x.message_id not in old_messages, new_replies))
        all_replies.extend(result)
        await self.save_replies(data=all_replies)
    #
    # @logger.catch
    # async def _get_unanswered(self, total_replies) -> List[dict]:
    #     return [elem for elem in total_replies if not elem.get("answered")]

    @logger.catch
    async def _get_old_replies_message_ids(self, all_replies: List[ReplyData]) -> List[str]:
        return list(map(
            lambda x: x.message_id,
            all_replies
        ))

    @logger.catch
    async def get_answered(self, target_id: str) -> List[ReplyData]:
        return [elem
                for elem in await self.load_replies()
                if elem.answer_text
                and not elem.answered
                and elem.target_id == target_id]

    @logger.catch
    async def update_text(self, message_id: str, text: str) -> bool:
        replies: List[ReplyData] = await self.load_replies()
        for elem in replies:
            if elem.message_id == message_id:
                elem.answer_text = text
                elem.answered = True
                elem.showed = True
                await self.save_replies(data=replies)
                return True

    @logger.catch
    async def update_answered_and_showed(self, message_id: str) -> bool:
        replies: List[ReplyData] = await self.load_replies()
        for elem in replies:
            if elem.message_id == message_id:
                elem.answered = True
                elem.showed = True
                await self.save_replies(data=replies)
                return True

    @logger.catch
    async def update_showed(self, message_id: str) -> bool:
        replies: List[ReplyData] = await self.load_replies()
        for elem in replies:
            if elem.message_id == message_id:
                elem.showed = True
                await self.save_replies(data=replies)
                return True

    async def load_replies(self) -> List[ReplyData]:
        return [ReplyData(**elem) for elem in await self.load()]

    async def save_replies(self, data: List[ReplyData]) -> None:
        await self.save(data=[elem.get_dict() for elem in data])
