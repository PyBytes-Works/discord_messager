from typing import List

from classes.redis_interface import RedisDB


class Replies(RedisDB):

    def __init__(self, redis_key: str):
        super().__init__(redis_key)

    async def update_replies(self, new_replies: List[dict]) -> List[dict]:
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

    async def get_replies(self) -> List[dict]:
        return await self.load()

    async def get_unanswered(self, target_id: str) -> List[dict]:
        return [elem
                for elem in await self.load()
                if str(elem.get("target_id")) == target_id]

    async def delete_answered(self, message_id: int):
        replies_without_answered: List[dict] = [elem
                                                for elem in await self.load()
                                                if str(elem.get("message_id")) != str(message_id)]
        await self.save(data=replies_without_answered)
