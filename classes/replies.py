from typing import List

from classes.redis_interface import RedisDB
from config import logger


class Replies(RedisDB):

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
    async def update_answered(self, message_id: str, text: str = '') -> bool:
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

