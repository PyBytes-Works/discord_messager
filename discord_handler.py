import datetime
import os
import random
from typing import List

import asyncio

import requests

from data_classes import users_data_storage, DataStore
from models import Token
from config import logger
from dotenv import load_dotenv

from utils import save_data_to_json, save_to_redis, load_from_redis


load_dotenv()

PROXY_USER = os.getenv("PROXY_USER")
PROXY_PASSWORD = os.getenv("PROXY_PASSWORD")


class MessageReceiver:

    """Выбирает токен для отправки сообщения и вызывает метод вызова сообщения,
    проверяет его ответ, и, если есть свободные токены - повторяет процесс.
    При ошибке возвращает ее в телеграм"""

    @logger.catch
    def __init__(self, datastore: 'DataStore', timer: float = 7):
        self.__datastore: 'DataStore' = datastore
        self.__timer: float = timer

    @logger.catch
    async def get_message(self) -> dict:
        """Получает данные из АПИ, выбирает случайное сообщение и возвращает ID сообщения
        и само сообщение"""

        result = {"work": True, "message": "ERROR"}
        selected_data: dict = self.__select_token_for_work()
        result_message: str = selected_data["message"]
        token: str = selected_data.get("token", None)

        if not token:
            result.update({"work": False, "message": result_message})
            return result
        user_message, message_id = await self.__get_user_message_from_redis(token=token)
        if message_id:
            self.__datastore.current_message_id = message_id
        else:
            data: dict = self.__get_data_from_api()
            if data:
                result_data: dict = random.choice(data.get("messages"))
                self.__datastore.current_message_id = int(result_data["id"])
                replies: list = data.get("replies", [{}])
                if replies:
                    await save_to_redis(telegram_id=self.__datastore.telegram_id, data=replies)
                    result.update(replies=replies)
        text_to_send = user_message if user_message else ''
        answer: str = MessageSender(datastore=self.__datastore).send_message(text=text_to_send)
        self.__datastore.current_message_id = 0
        if answer != "Message sent":
            result.update({"work": False, "message": answer, "token": token})
            return result
        # timer += random.randint(0, 4)
        logger.info(f"Пауза между отправкой сообщений: {self.__timer}")
        await asyncio.sleep(self.__timer)

        return result

    @logger.catch
    async def __get_user_message_from_redis(self, token: str) -> tuple:
        """Возвращает данные из Редиса"""

        answer: str = ''
        message_id = 0
        redis_data: List[dict] = await load_from_redis(telegram_id=self.__datastore.telegram_id)
        for elem in redis_data:
            if elem.get("token") == token:
                message_id = elem.get("message_id", 0)
                answer = elem.get("answer_text", '')
                break
        return answer, message_id

    @logger.catch
    def __select_token_for_work(self) -> dict:
        """
        Выбирает случайного токена дискорда из свободных, если нет свободных - пишет сообщение что
        свободных нет.
        """

        result: dict = {"message": "token ready"}
        all_tokens: List[dict] = Token.get_all_related_user_tokens(telegram_id=self.__datastore.telegram_id)
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
    def __get_data_from_api(self) -> dict:
        """Отправляет запрос к АПИ"""

        session = requests.Session()
        session.headers['authorization'] = self.__datastore.token
        limit = 100
        url = self.__datastore.channel_url + f'{self.__datastore.channel}/messages?limit={limit}'
        proxies = {
            "http": f"http://{PROXY_USER}:{PROXY_PASSWORD}@{self.__datastore.proxy}/"
        }
        response = session.get(url=url, proxies=proxies)
        status_code = response.status_code
        result = {}
        if status_code == 200:
            try:
                data = response.json()
            except Exception as err:
                logger.error(f"JSON ERROR: {err}")
            else:
                save_data_to_json(data=data)
                result: dict = self.__data_filter(data=data)
                print("LEN RESULT:", len(result))
        else:
            logger.error(f"API request error: {status_code}")

        return result

    @logger.catch
    def __data_filter(self, data: dict) -> dict:
        """Фильтрует полученные данные"""

        messages = []
        replies = [{}]
        result = {}
        summa = 0

        for elem in data:
            reply: str = elem.get("referenced_message", {}).get("author", {}).get("id", '')
            mentions: tuple = tuple(filter(lambda x: x.get("id", '') == self.__datastore.my_discord_id, elem.get("mentions", [])))
            author: str = elem.get("author")
            if any(mentions) or reply == self.__datastore.my_discord_id:
                if author not in Token.get_all_discord_id(token=self.__datastore.token):
                    replies.append({
                        "token": self.__datastore.token,
                        "author": author,
                        "text": elem.get("content", ''),
                        "id":  elem.get("id", '')
                    })

            message = elem.get("content")
            message_time = elem.get("timestamp")
            mes_time = datetime.datetime.fromisoformat(message_time).replace(tzinfo=None)
            if self.__datastore.mate_id == elem["author"]["id"]:
                delta = datetime.datetime.utcnow().replace(tzinfo=None) - mes_time
                if delta.seconds < self.__datastore.last_message_time:
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
        result.update(messages=messages, replies=replies)
        print("Filtered result:", result)
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
        logger.info(f"Результат отправки сообщения в дискорд: {answer}")
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
        url = self.__datastore.channel_url + f'{self.__datastore.channel}/messages?'
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
            try:
                data = response.json()
            except Exception as err:
                logger.warning(err)
                return f"JSON ERROR {err}"
            else:
                logger.info(f"Data received: {len(data)}")
                answer = "Message sent"
        else:
            answer = f"API request error: {status_code}"
            logger.error(answer)

        return answer
