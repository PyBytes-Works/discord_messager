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
        self.timeout_sec: int = 1000

    async def _send_request_do_redis_db(self, key: str, mate_id: str = '', data: list = None) -> list:
        """Запрашивает или записывает данные в редис, возвращает список если запрашивали"""

        result: list = []
        name: str = mate_id if mate_id else self.redis_key
        data: list = data if data else self.data
        log_data: str = (
            f"\nData:"
            f"\nKey: {key}"
            f"\nName: {name}"
            f"\nMate id: {mate_id}"
            f"\nData: \n{data}")
        error_text: str = ''
        try:
            async with self.redis_db.client() as conn:
                if key == "set":
                    await conn.set(
                        name=name, value=json.dumps(data), ex=self.timeout_sec)
                elif key == "get":
                    data: str = await conn.get(name)
                    if data:
                        try:
                            result: list = json.loads(data)
                        except TypeError as err:
                            error_text = f"{err}"
                        except Exception as err:
                            error_text = f"JSON error: {err}"
                elif key == 'del':
                    await conn.delete(self.redis_key, mate_id)
                else:
                    raise ValueError(f"(key=???) error")
        except ConnectionRefusedError as err:
            error_text = (f"Unable to connect to redis, data: '{self.data}' not saved!"
                          f"\n {err}")
        except aioredis.exceptions.ConnectionError as err:
            error_text = f"Connection error: {err}"
        except Exception as err:
            error_text = f"Exception Error: {err}"
        if error_text:
            logger.error(error_text + log_data)
        return result

    @logger.catch
    async def save(self, data: list, timeout_sec: int = 0) -> None:
        """Сериализует данные и сохраняет в Редис. Устанавливает время хранения в секундах.
        Возвращает кол-во записей."""

        self.data: list = data
        if timeout_sec:
            self.timeout_sec: int = timeout_sec

        await self._send_request_do_redis_db(key="set")

    @logger.catch
    async def load(self) -> list:
        """Возвращает десериализованные данные из Редис (список)"""

        return await self._send_request_do_redis_db(key="get")

    @logger.catch
    async def delete(self, mate_id: str) -> List[dict]:
        """Удаляет данные из Редис для себя и напарника"""

        return await self._send_request_do_redis_db(key="del", mate_id=mate_id)
