import json

import aioredis
from typing import List

from config import logger
from db_config import REDIS_CLIENT


class RedisDB:
    """Сохраняет и загружает данные из редис."""

    def __init__(self, redis_key: str):
        self.redis = REDIS_CLIENT
        self.redis_key: str = redis_key
        self.data: list = []
        self.timeout_sec: int = 300

    @logger.catch()
    async def _send_request_do_redis_db(
            self, key: str, mate_id: str = '', data: list = None) -> list:
        """Запрашивает или записывает данные в редис, возвращает список если запрашивали"""

        result: list = []
        name: str = mate_id if mate_id else self.redis_key
        if not name:
            return []
        data: list = data if data else self.data
        log_data: str = (
            f"\nData:"
            f"\nKey: {key}"
            f"\nName: {name}"
            f"\nMate id: {mate_id}"
            f"\nData: \n{data}")
        error_text: str = ''
        try:
            if key == "set":
                await self.redis.set(
                    name=name, value=json.dumps(data), ex=self.timeout_sec)
            elif key == "get":
                data: str = await self.redis.get(name)
                if data:
                    try:
                        result: list = json.loads(data)
                    except TypeError as err:
                        error_text = f"{err}"
                    except Exception as err:
                        error_text = f"JSON error: {err}"
            elif key == 'del':
                await self.redis.delete(self.redis_key, mate_id)
            else:
                logger.error(f"No key for Redis work.")
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
    async def delete_key(self, mate_id: str) -> List[dict]:
        """Удаляет данные из Редис для себя и напарника"""

        return await self._send_request_do_redis_db(key="del", mate_id=mate_id)

    @logger.catch
    async def health_check(self) -> bool:
        """Проверяет работу Редис"""

        check_data = ['test']
        await self.save(check_data, 60)
        result = await self.load()
        return check_data == result


