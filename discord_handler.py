import datetime
import os
import random
from typing import List, Tuple

import asyncio
import aiohttp
import requests
import aiohttp.client_exceptions
import aiohttp.http_exceptions

from data_classes import users_data_storage, DataStore
from models import Token
from config import logger
from dotenv import load_dotenv

from utils import save_data_to_json, save_to_redis, load_from_redis


load_dotenv()

PROXY_USER = os.getenv("PROXY_USER")
PROXY_PASSWORD = os.getenv("PROXY_PASSWORD")


class MessageReceiver:

    __EXCEPTIONS: tuple = (
        asyncio.exceptions.TimeoutError,
        aiohttp.client_exceptions.ServerDisconnectedError,
        aiohttp.client_exceptions.ClientProxyConnectionError,
        aiohttp.client_exceptions.ClientHttpProxyError,
        aiohttp.client_exceptions.ClientOSError,
        aiohttp.client_exceptions.TooManyRedirects,
        ConnectionResetError
    )

    """Выбирает токен для отправки сообщения и вызывает метод вызова сообщения,
    проверяет его ответ, и, если есть свободные токены - повторяет процесс.
    При ошибке возвращает ее в телеграм"""

    @logger.catch
    def __init__(self, datastore: 'DataStore', timer: float = 7):
        self.__datastore: 'DataStore' = datastore
        self.__timer: float = timer

    @classmethod
    async def check_user_data(cls, token: str, proxy: str, channel: int) -> dict:
        """Returns checked dictionary for user data

        Save valid data to instance variables """

        result = {"token": await cls.__check_token(token=token, proxy=proxy, channel=channel)}
        if result["token"] != "bad token":
            result["channel"] = channel

        return result

    @classmethod
    async def __check_token(cls, token: str, proxy: str, channel: int) -> str:
        """Returns valid token else 'bad token'"""

        async with aiohttp.ClientSession() as session:
            session.headers['authorization']: str = token
            limit: int = 1
            url: str = DataStore.get_channel_url() + f'{channel}/messages?limit={limit}'
            result: str = 'bad token'
            proxy_data = f"http://{PROXY_USER}:{PROXY_PASSWORD}@{proxy}/"
            try:
                async with session.get(url=url, proxy=proxy_data, ssl=False, timeout=10) as response:
                # async with session.get(url=url, timeout=10) as response:
                    if response.status == 200:
                        result = token
            except cls.__EXCEPTIONS as err:
                logger.info(f"Token check Error: {err}")
            except aiohttp.http_exceptions.BadHttpMessage as err:
                logger.error("МУДАК ПРОВЕРЬ ПОРТ ПРОКСИ!!!", err)

        return result

    @staticmethod
    @logger.catch
    def __get_current_message_id(data: dict) -> int:
        message_id = 0
        filtered_messages: list = data.get("messages", [])
        if filtered_messages:
            result_data: dict = random.choice(filtered_messages)
            message_id = int(result_data.get("id"))

        return message_id

    @logger.catch
    async def get_message(self) -> dict:
        """Получает данные из АПИ, выбирает случайное сообщение и возвращает ID сообщения
        и само сообщение"""

        result = {"work": True, "message": "ERROR"}
        token_data: dict = await self.__select_token_for_work()
        result_message: str = token_data.get("message")
        if result_message == "no pairs":
            result.update(token_data)
            return result

        token: str = token_data.get("token", '')
        if not token:
            result.update({"work": False, "message": result_message})
            return result

        user_message, message_id = await self.__get_user_message_from_redis(token=token)
        # logger.info(f"Сообщение из редис {user_message} для {message_id}")
        if message_id:
            self.__datastore.current_message_id = message_id
        else:
            filtered_data: dict = await self.__get_data_from_api()
            # logger.info(f"Отфильтровали данные {filtered_data}")
            if filtered_data:
                replies: List[dict] = filtered_data.get("replies", [])
                logger.info(f"Новые реплаи {replies}")
                if replies:
                    result.update({"replies": replies})
                self.__datastore.current_message_id = self.__get_current_message_id(data=filtered_data)
        text_to_send = user_message if user_message else ''
        answer: str = MessageSender(datastore=self.__datastore).send_message(text=text_to_send)
        self.__datastore.current_message_id = 0
        # logger.info(f"Ответ после отсылки сообщения {answer}")
        if answer != "Message sent":
            result.update({"work": False, "message": answer, "token": token})
            return result
        # logger.info(f"Пауза между отправкой сообщений: {self.__timer}")
        await asyncio.sleep(self.__timer)

        return result

    @logger.catch
    async def __get_user_message_from_redis(self, token: str) -> Tuple[str, int]:
        """Возвращает данные из Редиса"""

        answer: str = ''
        message_id = 0
        redis_data: List[dict] = await load_from_redis(telegram_id=self.__datastore.telegram_id)
        for elem in redis_data:
            answered = elem.get("answered", False)
            if not answered:
                if elem.get("token") == token:
                    answer = elem.get("answer_text", '')
                    if answer:
                        message_id = elem.get("message_id", 0)
                        elem.update({"answered": True})
                        await save_to_redis(telegram_id=self.__datastore.telegram_id, data=redis_data)
                        break

        return answer, message_id

    @logger.catch
    async def __select_token_for_work(self) -> dict:
        """
        Выбирает случайного токена дискорда из свободных, если нет свободных - пишет сообщение что
        свободных нет.
        """

        result: dict = {"message": "token ready"}
        all_tokens: List[dict] = Token.get_all_related_user_tokens(telegram_id=self.__datastore.telegram_id)
        if not all_tokens:
            result["message"] = "no pairs"
            return result
        current_time: int = int(datetime.datetime.now().timestamp())
        workers: list = [
            key
            for elem in all_tokens
            for key, value in elem.items()
            if current_time > value["time"] + value["cooldown"]
        ]
        if workers:
            random_token: str = random.choice(workers)
            result["token"]: str = random_token
            self.__datastore.save_token_data(random_token)
        else:
            min_token_data = {}
            for elem in all_tokens:
                min_token_data: dict = min(elem.items(), key=lambda x: x[1].get('time'))
            token: str = tuple(min_token_data)[0]
            self.__datastore.save_token_data(token)
            min_token_time: int = Token.get_time_by_token(token)
            delay: int = self.__datastore.cooldown - abs(min_token_time - current_time)
            self.__datastore.delay = delay
            text = "секунд"
            if delay > 60:
                minutes: int = delay // 60
                seconds: int = delay % 60
                if minutes < 10:
                    minutes: str = f"0{minutes}"
                if seconds < 10:
                    seconds: str = f'0{seconds}'
                delay: str = f"{minutes}:{seconds}"
                text = "минут"
            result["message"] = f"Все токены отработали. Следующий старт через {delay} {text}."

        return result

    @logger.catch
    async def __get_data_from_api(self) -> dict:
        """Отправляет запрос к АПИ"""

        session = requests.Session()
        session.headers['authorization']: str = self.__datastore.token
        limit: int = 100
        url: str = self.__datastore.get_channel_url() + f'{self.__datastore.channel}/messages?limit={limit}'
        proxies: dict = {
            "http": f"http://{PROXY_USER}:{PROXY_PASSWORD}@{self.__datastore.proxy}/"
        }
        response = session.get(url=url, proxies=proxies)
        status_code: int = response.status_code
        result: dict = {}
        if status_code == 200:
            try:
                data: List[dict] = response.json()
            except Exception as err:
                logger.error(f"JSON ERROR: {err}")
            else:
                # save_data_to_json(data=data)
                result: dict = await self.__data_filter(data=data)
        else:
            logger.error(f"API request error: {status_code}")

        return result

    @logger.catch
    async def __data_filter(self, data: List[dict]) -> dict:
        """Фильтрует полученные данные"""
        messages = []
        replies = []
        result = {}
        # FIXME ЗАЛИПУХА
        if not data:
            return result
        summa = 0
        for elem in data:
            message: str = elem.get("content")
            message_time: 'datetime' = elem.get("timestamp")
            mes_time = datetime.datetime.fromisoformat(message_time).replace(tzinfo=None)
            delta = datetime.datetime.utcnow().replace(tzinfo=None) - mes_time
            if delta.seconds < self.__datastore.last_message_time:
                filtered_replies: dict = self.__replies_filter(data=elem)
                if filtered_replies:
                    replies.append(filtered_replies)
                is_author_mate: bool = str(self.__datastore.mate_id) == str(elem["author"]["id"])
                my_message: bool = str(elem["author"]["id"]) == str(self.__datastore.my_discord_id)
                if is_author_mate and not my_message:
                    summa += len(message)
                    messages.append(
                        {
                            "id": elem.get("id"),
                            "message": message,
                            "channel_id": elem.get("channel_id"),
                            "author": elem.get("author"),
                            "timestamp": message_time
                        }
                    )
        if messages:
            result.update({"messages": messages})
        if replies:
            replies: List[dict] = await self.__update_replies_to_redis(replies)
            result.update({"replies": replies})

        return result

    @logger.catch
    async def __update_replies_to_redis(self, data: list) -> list:
        """Возвращает разницу между старыми и новыми данными в редисе,
        записывает полные данные в редис"""

        total_replies: List[dict] = await load_from_redis(telegram_id=self.__datastore.telegram_id)
        replies: List[dict] = [elem for elem in data if elem not in total_replies]
        total_replies.extend(replies)
        await save_to_redis(telegram_id=self.__datastore.telegram_id, data=total_replies)

        return replies

    def __replies_filter(self, data: dict) -> dict:
        """Возвращает реплаи не из нашего села."""

        import copy
        result = {}
        elem = copy.deepcopy(data)
        if isinstance(elem, dict) and elem:
            reply_for_author_id: str = 'Базовая строка'
            try:
                ref_messages: dict = elem.get("referenced_message", {})
                print(ref_messages)
                if ref_messages:
                    ref_messages_author: dict = ref_messages.get("author", {})
                    print(ref_messages_author)
                    if ref_messages_author:
                        reply_for_author_id: str = ref_messages_author.get("id", '')
                        print(reply_for_author_id)
            except AttributeError as err:
                logger.error(f"F: __replies_filter: Ошибка какая то хер пойми."
                             f"\nreply_for_author_id: {reply_for_author_id}"
                             f"\nelem: {elem}", err)
            except KeyError as err:
                logger.error(f"F: __replies_filter: Ошибка какая то хер пойми. ТЕПЕРЬ С КЛЮЧЕМ:"
                             f"\n", err)
                return result
            mentions: tuple = tuple(
                filter(
                    lambda x: int(x.get("id", '')) == int(self.__datastore.my_discord_id),
                    elem.get("mentions", [])
                )
            )
            author: str = elem.get("author", {}).get("username", '')
            author_id: str = elem.get("author", {}).get("id", '')
            message_for_me: bool = reply_for_author_id == self.__datastore.my_discord_id
            if any(mentions) or message_for_me:
                if author_id not in Token.get_all_discord_id(token=self.__datastore.token):
                    result.update({
                        "token": self.__datastore.token,
                        "author": author,
                        "text": elem.get("content", ''),
                        "message_id": elem.get("id", '')
                    })

        return result


class MessageSender:
    """Отправляет сообщение в дискорд-канал в ответ на сообщение
    связанного токена
    Возвращает сообщение об ошибке или об успехе"""

    @logger.catch
    def __init__(self, datastore: 'DataStore'):
        self.__datastore: 'DataStore' = datastore

    @logger.catch
    def send_message(self, text: str = '') -> str:
        """Отправляет данные в канал дискорда, возвращает результат отправки."""

        answer: str = self.__send_message_to_discord_channel(text=text)
        # logger.info(f"Результат отправки сообщения в дискорд: {answer}")
        Token.update_token_time(token=self.__datastore.token)

        return answer

    @logger.catch
    def __send_message_to_discord_channel(self, text: str = '') -> str:
        """Формирует данные для отправки, возвращает результат отправки."""

        if not text:
            text = users_data_storage.get_random_message_from_vocabulary()
        data = {
            "content": text,
            "tts": "false",
        }
        if self.__datastore.current_message_id:
            data.update({
                "content": text,
                "tts": "false",
                "message_reference":
                    {
                        "guild_id": self.__datastore.guild,
                        "channel_id": self.__datastore.channel,
                        "message_id": self.__datastore.current_message_id
                    },
                "allowed_mentions":
                    {
                        "parse": [
                            "users",
                            "roles",
                            "everyone"
                        ],
                        "replied_user": "false"
                    }
            })

        return self.__send_data_to_api(data=data)

    @logger.catch
    def __send_data_to_api(self, data):
        """Отправляет данные в дискорд канал"""

        session = requests.Session()
        session.headers['authorization'] = self.__datastore.token
        url = self.__datastore.get_channel_url() + f'{self.__datastore.channel}/messages?'
        proxies = {
            "http": f"http://{PROXY_USER}:{PROXY_PASSWORD}@{self.__datastore.proxy}/",
        }
        try:
            response = session.post(url=url, json=data, proxies=proxies)
        except Exception as err:
            return f'Ошибка отправки сообщения: {err}'
        status_code = response.status_code
        if status_code == 204:
            answer = "Ошибка 204, нет содержимого."
        elif status_code == 200:
            answer = "Message sent"
        else:
            answer = f"API request error: {status_code}"
            logger.error(answer)

        return answer
