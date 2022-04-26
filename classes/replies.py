from typing import List

from classes.redis_interface import RedisDB


class Replies:

    def __init__(self, telegram_id: str):
        self._telegram_id: str = telegram_id

    async def get_replies(self) -> List[dict]:
        pass

    async def update_replies(self):
        pass

    async def get_unanswered(self) -> List[dict]:
        pass


