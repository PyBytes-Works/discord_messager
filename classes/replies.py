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
        old_messages: List[str] = list(map(lambda x: x.get("message_id"), total_replies))
        result: List[
            dict] = list(filter(lambda x: x.get("message_id") not in old_messages, new_replies))
        total_replies.extend(result)
        await self.save(data=total_replies)

        return result

    @logger.catch
    async def get_answered(self, target_id: str) -> List[dict]:
        return [elem
                for elem in await self.load()
                if elem.get("answered")
                and str(elem.get("target_id")) == target_id]

    @logger.catch
    async def update_answered_or_showed(self, message_id: str, text: str = '') -> bool:
        redis_data: List[dict] = await self.load()
        for elem in redis_data:
            if str(elem.get("message_id")) == str(message_id):
                if text:
                    elem.update(
                        {
                            "answer_text": text,
                            "showed": True,
                            "answered": True
                        }
                    )
                else:
                    elem.update(showed=True)
                await self.save(data=redis_data)
                return True

