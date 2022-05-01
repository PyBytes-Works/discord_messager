from typing import List

from classes.redis_interface import RedisDB
from config import logger


class RepliesManager(RedisDB):

    """Класс для работы с реплаями - загрузка, сохранение, фильтрация"""

    def __init__(self: 'RepliesManager', redis_key: str):
        super().__init__(redis_key)

    async def get_not_showed(self: 'RepliesManager') -> List[dict]:
        """Возвращает список свежих реплаев для обработки"""
        return [
            elem
            for elem in await self.load()
            if not elem.get("showed")
        ]

    @logger.catch
    async def update_new_replies(self: 'RepliesManager', new_replies: List[dict]) -> None:
        """Возвращает разницу между старыми и новыми данными в редисе,
        записывает полные данные в редис"""

        if not new_replies:
            return
        all_replies: List[dict] = await self.load()
        old_messages: List[str] = await self._get_old_replies_message_ids(all_replies)
        result: List[dict] = list(filter(
            lambda x: x.get("message_id") not in old_messages, new_replies))
        all_replies.extend(result)
        await self.save(data=all_replies)

    @logger.catch
    async def _get_old_replies_message_ids(
            self: 'RepliesManager', all_replies: List[dict]) -> List[str]:
        """Возвращает список ИД-номеров сообщений"""

        return list(map(
            lambda x: x.get("message_id"),
            all_replies
        ))

    @logger.catch
    async def get_not_answered_with_text(self: 'RepliesManager', target_id: str) -> List[dict]:
        """Возвращает список словарей с непустым полем text"""

        return [elem
                for elem in await self.load()
                if elem.get("answer_text")
                and not elem.get("answered")
                and elem.get("target_id") == target_id]

    @logger.catch
    async def update_text(self: 'RepliesManager', message_id: str, text: str) -> bool:
        """Добавляет поле text в словарь с message_id и сохраняет список в Редис"""

        replies: List[dict] = await self.load()
        for elem in replies:
            if elem.get("message_id") == message_id:
                elem.update(answer_text=text)
                await self.save(data=replies)
                return True

    @logger.catch
    async def update_answered(self: 'RepliesManager', message_id: str) -> bool:
        """Добавляет поле answered в словарь с message_id и сохраняет список в Редис"""

        replies: List[dict] = await self.load()
        for elem in replies:
            if elem.get("message_id") == message_id:
                elem.update(answered=True)
                await self.save(data=replies)
                return True

    @logger.catch
    async def update_showed(self: 'RepliesManager', message_id: str) -> bool:
        """Добавляет поле showed в словарь с message_id и сохраняет список в Редис"""

        replies: List[dict] = await self.load()
        for elem in replies:
            if elem.get("message_id") == message_id:
                elem.update(showed=True)
                await self.save(data=replies)
                return True
