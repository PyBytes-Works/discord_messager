from typing import List

from classes.redis_interface import RedisDB
from config import logger


class ReplyData:

    """Reply dataclass"""

    def __init__(self, **kwargs):
        self.token: bool = kwargs.get("token", False)
        self.author: bool = kwargs.get("author", False)
        self.text: bool = kwargs.get("text", False)
        self.message_id: bool = kwargs.get("message_id", False)
        self.to_message: bool = kwargs.get("to_message", False)
        self.to_user: bool = kwargs.get("to_user", False)
        self.target_id: bool = kwargs.get("target_id", False)
        self.showed: bool = False
        self.answered: bool = False

    def set_answered(self):
        self.answered = True

    def set_showed(self):
        self.showed = True

    def get_dict(self) -> dict:
        return self.__dict__


class RepliesManager(RedisDB):

    # TODO Сделать дата-класс реплаев

    def __init__(self, redis_key: str):
        super().__init__(redis_key)

    @logger.catch
    async def get_difference_and_update(self, new_replies: List[dict]) -> List[dict]:
        """Возвращает разницу между старыми и новыми данными в редисе,
        записывает полные данные в редис"""

        if not new_replies:
            return []
        total_replies: List[dict] = await self.load()
        unanswered: List[dict] = await self._get_unanswered(total_replies)
        old_messages: List[str] = await self._get_old_replies(unanswered)
        result: List[dict] = list(filter(
            lambda x: x.get("message_id") not in old_messages, new_replies))
        total_replies.extend(result)
        await self.save(data=total_replies)

        return result

    @logger.catch
    async def _get_unanswered(self, total_replies) -> List[dict]:
        return [elem for elem in total_replies if not elem.get("answered")]

    @logger.catch
    async def _get_old_replies(self, unanswered) -> List[str]:
        return list(map(
            lambda x: x.get("message_id"),
            unanswered
        ))

    @logger.catch
    async def get_answered(self, target_id: str) -> List[dict]:
        return [elem
                for elem in await self.load()
                if elem.get("answer_text")
                and not elem.get("answered")
                and str(elem.get("target_id")) == target_id]

    @logger.catch
    async def update_text(self, message_id: str, text: str) -> bool:
        redis_data: List[dict] = await self.load()
        for elem in redis_data:
            if str(elem.get("message_id")) == str(message_id):
                elem.update(answer_text=text)
                await self.save(data=redis_data)
                return True

    @logger.catch
    async def update_answered(self, message_id: str) -> bool:
        redis_data: List[dict] = await self.load()
        for elem in redis_data:
            if str(elem.get("message_id")) == str(message_id):
                elem.update(answered=True)
                await self.save(data=redis_data)
                return True

    @logger.catch
    async def update_showed(self, message_id: str) -> bool:
        redis_data: List[dict] = await self.load()
        for elem in redis_data:
            if str(elem.get("message_id")) == str(message_id):
                elem.update(showed=True)
                await self.save(data=redis_data)
                return True
