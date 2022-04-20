import json

import aioredis
from typing import Optional, List

from config import logger, REDIS_DB


class RedisDB:
    """Сохраняет и загружает данные из редис."""

    def __init__(self, redis_key: str):
        self.redis_db = aioredis.from_url(url=REDIS_DB, encoding="utf-8", decode_responses=True)
        self.redis_key: str = redis_key
        self.data: list = []
        self.timeout_sec: int = 0

    @logger.catch
    async def __send_request_do_redis_db(self, key: str, mate_id: str = '') -> Optional[list]:
        """Запрашивает или записывает данные в редис, возвращает список если запрашивали"""

        logger.debug(f"Запрос в редис: "
                     f"\nUSER: {self.redis_key}")
        result: List[dict] = []
        try:
            async with self.redis_db.client() as conn:
                if key == "set":
                    logger.debug(f"\nDATA: {self.data}")
                    await conn.set(
                        name=self.redis_key, value=json.dumps(self.data), ex=self.timeout_sec)
                elif key == "get":
                    data: str = await conn.get(self.redis_key)
                    if data:
                        try:
                            result: List[dict] = json.loads(data)
                        except TypeError as err:
                            logger.error(f"F: load_from_redis: {err}", err)
                        except Exception as err:
                            logger.error(f"RedisInterface.__get_or_set_from_db(): JSON error: {err}")
                elif key == 'del':
                    await conn.delete(self.redis_key, mate_id)
                else:
                    raise ValueError("RedisInterface.__get_or_set_from_db(key=???) error")
        except ConnectionRefusedError as err:
            logger.error(f"Unable to connect to redis, data: '{self.data}' not saved!", err)
        except aioredis.exceptions.ConnectionError as err:
            logger.error(f"RedisInterface.__get_or_set_from_db(): Connection error: {err}")
        except Exception as err:
            logger.error(f"RedisInterface.__get_or_set_from_db(): {err}")
        return result

    @logger.catch
    async def save(self, data: list, timeout_sec: int = 1000) -> None:
        """Сериализует данные и сохраняет в Редис. Устанавливает время хранения в секундах.
        Возвращает кол-во записей."""

        self.data: list = data
        self.timeout_sec: int = timeout_sec

        await self.__send_request_do_redis_db(key="set")

    @logger.catch
    async def load(self) -> List[dict]:
        """Возвращает десериализованные данные из Редис (список)"""

        return await self.__send_request_do_redis_db(key="get")

    @logger.catch
    async def delete(self, mate_id: str) -> List[dict]:
        """Удаляет данные из Редис для себя и напарника"""

        return await self.__send_request_do_redis_db(key="del", mate_id=mate_id)
