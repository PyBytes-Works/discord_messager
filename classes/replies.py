from typing import List, Set

from classes.redis_interface import RedisDB
from config import logger


class Replies(RedisDB):

    def __init__(self, redis_key: str):
        super().__init__(redis_key)

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

    async def get_answered(self, target_id: str) -> List[dict]:
        return [elem
                for elem in await self.load()
                if elem.get("answered")
                and str(elem.get("target_id")) == target_id]

    async def update_answered(self, message_id: str, text: str) -> bool:
        redis_data: List[dict] = await self.load()
        for elem in redis_data:
            if str(elem.get("message_id")) == str(message_id):
                elem.update(
                    {
                        "answer_text": text,
                        "answered": True
                    }
                )
                await self.save(data=redis_data)
                return True

    async def update_showed(self, message_id: str) -> bool:
        redis_data: List[dict] = await self.load()
        for elem in redis_data:
            if str(elem.get("message_id")) == str(message_id):
                elem.update(
                    {
                        "showed": True
                    }
                )
                await self.save(data=redis_data)
                return True


    # if not await Replies(redis_key=user_telegram_id).update_reply(message_id=message_id, text=message.text):
    #     logger.warning("f: send_message_to_reply_handler: elem in Redis data not found or timeout error")
    #     await message.answer('Время хранения данных истекло.', reply_markup=cancel_keyboard())


    # async def get_replies(self) -> List[dict]:
    #     return await self.load()
    #

    #
    # async def delete_answered(self, message_id: str):
    #     result: List[dict] = [elem
    #                           for elem in await self.get_answered_list()
    #                           if str(elem.get("message_id")) != str(message_id)
    #                           ]
    #     await self.save(data=result)
    #
    # async def add_to_unanswered_list(self, new_replies: List[dict]) -> None:
    #     new_replies_set: Set[str] = set(map(lambda x: x.get("message_id"), new_replies))
    #     logger.debug(f"\n\n\t\tnew_replies_set: {new_replies_set}")
    #     unanswered: Set[str] = set(await self.get_unanswered_list())
    #     logger.debug(f"\n\t\tunanswered: {unanswered}")
    #     data: list = list(new_replies_set.union(unanswered))
    #     logger.debug(f"\n\t\tdata for saving: {data}\n")
    #
    #     await self._send_request_do_redis_db(
    #         key='set', mate_id=f'unanswered_{self.redis_key}', data=data)
    # #
    # # async def get_unanswered_list(self) -> List[str]:
    # #     return await self._send_request_do_redis_db(
    # #         key='get', mate_id=f'unanswered_{self.redis_key}')
    #
    # async def add_to_answered_list(self, reply_data: dict) -> None:
    #     answered: List[dict] = await self.get_answered_list()
    #     answered.append(reply_data)
    #     await self._send_request_do_redis_db(
    #         key='set', mate_id=f'answered_{self.redis_key}', data=answered)
    #
    # async def get_answered_list(self) -> List[dict]:
    #     return await self._send_request_do_redis_db(
    #         key='get', mate_id=f'answered_{self.redis_key}')
    #
    # async def get_answered(self, target_id: str) -> List[dict]:
    #     return [elem
    #             for elem in await self.load()
    #             if str(elem.get("target_id")) == target_id
    #             and str(elem.get("message_id")) not in await self.get_answered_list()]
