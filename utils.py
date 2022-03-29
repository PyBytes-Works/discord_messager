import aiogram
import aioredis
import json
import os
import random
import string
import aiogram.utils.exceptions

from typing import Union, Optional, List
from config import logger, bot, admins_list, REDIS_DB


def save_data_to_json(data, file_name: str = "data.json", key: str = 'w'):
    if key == 'w':
        with open(file_name, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    elif key == 'a':
        result = {}
        if os.path.exists(file_name):
            with open(file_name, 'r', encoding='utf-8') as f:
                result: dict = json.load(f)
        result.update(data)
        save_data_to_json(data=result, file_name=file_name, key='w')

    # print(file_name, "saved.")


def save_data_to_txt(data: Union[dict, list], file_name: str = "data.json"):
    with open(file_name, 'w', encoding='utf-8') as f:
        data = "\n".join(data)
        f.write(data)

    print(file_name, "saved.")


def check_is_int(text: str) -> int:
    """Проверяет что в строке пришло положительное число и возвращает его обратно если да"""

    if text.isdigit():
        if int(text) > 0:
            return int(text)

    return 0


@logger.catch
def get_token(key: str) -> str:
    """Возвращает новый сгенерированный токен"""

    result = ''
    if key == "user":
        result = "new_user_"
    if key == "subscribe":
        result = "subscribe_"
    return result + ''.join(random.choices(string.ascii_letters, k=50))


@logger.catch
def add_new_token(tokens: dict) -> None:
    """Добавляет новый токен и имя, к которому он привязан, в файл"""

    if os.path.exists("tokens.json"):
        with open("tokens.json", 'r', encoding="utf-8") as f:
            old_tokens = json.load(f)
            if old_tokens:
                tokens.update(old_tokens)

    with open("tokens.json", 'w', encoding="utf-8") as f:
        json.dump(tokens, f, indent=4, ensure_ascii=False)


@logger.catch
def delete_used_token(token: str) -> dict:
    """Удаляет использованный токен из файла, возвращает имя пользователя"""

    user_data = {}
    tokens = {}
    if os.path.exists("tokens.json"):
        with open("tokens.json", "r", encoding="utf-8") as f:
            data = f.read().strip()
            if data:
                tokens = json.loads(data)
                if token in tokens:
                    user_data = tokens.pop(token)

    with open("tokens.json", "w", encoding="utf-8") as f:
        json.dump(tokens, f, indent=4, ensure_ascii=False)

    return user_data


async def send_report_to_admins(text: str) -> None:
    """Отправляет сообщение в телеграме всем администраторам из списка"""

    text = f'[Рассылка][Superusers]: {text}'
    for admin_id in admins_list:
        try:
            await bot.send_message(chat_id=admin_id, text=text)
        except aiogram.utils.exceptions.ChatNotFound as err:
            logger.error(f"Не смог отправить сообщение пользователю {admin_id}.", err)


class RedisInterface:
    """Сохраняет и загружает данные из редис."""

    def __init__(self, telegram_id: str):
        self.redis_db = aioredis.Redis.from_url(url=REDIS_DB, encoding="utf-8", decode_responses=True)
        self.telegram_id: str = telegram_id
        self.data: list = []
        self.timeout_sec = 0

    async def __get_or_set_from_db(self, key: str) -> Optional[list]:
        result: List[dict] = []

        try:
            async with self.redis_db.client() as conn:
                if key == "set":
                    await conn.set(
                        name=self.telegram_id, value=json.dumps(self.data), ex=self.timeout_sec)
                elif key == "get":
                    data = await conn.get(self.telegram_id)
                    if data:
                        try:
                            result: List[dict] = json.loads(data)
                        except TypeError as err:
                            logger.error(f"F: load_from_redis: {err}", err)
                else:
                    raise ValueError("RedisInterface.__get_or_set_from_db(key=???) error")
        except ConnectionRefusedError as err:
            logger.error(f"Unable to connect to redis, data: '{self.data}' not saved!", err)
        except aioredis.exceptions.ConnectionError as err:
            logger.error(f"RedisInterface.__get_or_set_from_db(): Connection error: {err}")

        return result

    async def save(self, data: list, timeout_sec: int = 3600) -> None:
        """Сериализует данные и сохраняет в Редис. Устанавливает время хранения в секундах.
        Возвращает кол-во записей."""

        self.data: list = data
        self.timeout_sec: int = timeout_sec

        await self.__get_or_set_from_db(key="set")

    async def load(self) -> List[dict]:
        """Возвращает десериализованные данные из Редис"""

        return await self.__get_or_set_from_db(key="get")
