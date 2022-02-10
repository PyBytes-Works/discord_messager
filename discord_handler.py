import datetime
import os
import random
from typing import List

import asyncio

import requests

from data_classes import users_data_storage, DataStore
from models import UserTokenDiscord
from config import logger
from dotenv import load_dotenv

from utils import save_data_to_json, save_to_redis


load_dotenv()

PROXY_USER = os.getenv("PROXY_USER")
PROXY_PASSWORD = os.getenv("PROXY_PASSWORD")


class MessageReceiver:

    """Выбирает токен для отправки сообщения и вызывает метод вызова сообщения,
    проверяет его ответ, и, если есть свободные токены - повторяет процесс.
    При ошибке возвращает ее в телеграм"""

    @classmethod
    @logger.catch
    async def get_message(cls, datastore: 'DataStore', timer: float = 7) -> dict:
        """Получает данные из АПИ, выбирает случайное сообщение и возвращает ID сообщения
        и само сообщение"""
        result = {"work": True, "message": "ERROR"}
        selected_data: dict = cls.__select_token_for_work(datastore=datastore)
        result_message: str = selected_data["message"]
        token: str = selected_data.get("token", None)

        if not token:
            result.update({"work": False, "message": result_message})
            return result
        data: dict = cls.__get_data_from_api(datastore=datastore)
        if data:
            result_data: dict = cls.__get_random_message(data.get("messages"))
            datastore.current_message_id = int(result_data["id"])
            replies: list = data.get("replies", [{}])
            if replies:
                await save_to_redis(telegram_id=datastore.telegram_id, data=replies, timeout=600)
                result.update(replies=replies)
        answer = MessageSender(datastore=datastore).send_message()
        datastore.current_message_id = 0
        if answer != "Message sent":
            result.update({"work": False, "message": answer, "token": token})
            return result
        timer += random.randint(0, 4)
        logger.info(f"Пауза между отправкой сообщений: {timer}")
        await asyncio.sleep(timer)

        return result

    @classmethod
    @logger.catch
    def __select_token_for_work(cls, datastore: 'DataStore') -> dict:
        """
        Выбирает случайного токена дискорда из свободных, если нет свободных - пишет сообщение что
        свободных нет.
        """
        result: dict = {"message": "token ready"}
        all_tokens: List[dict] = UserTokenDiscord.get_all_user_tokens(telegram_id=datastore.telegram_id)
        current_time: int = int(datetime.datetime.now().timestamp())
        tokens_for_job: list = [
            key
            for elem in all_tokens
            for key, value in elem.items()
            if current_time > value["time"] + value["cooldown"]
        ]
        if tokens_for_job:
            random_token: str = random.choice(tokens_for_job)
            result["token"]: str = random_token
            datastore.save_token_data(random_token)
        else:
            min_token_data = {}
            for elem in all_tokens:
                min_token_data: dict = min(elem.items(), key=lambda x: x[1].get('time'))
            token: str = tuple(min_token_data)[0]
            datastore.save_token_data(token)
            min_token_time: int = UserTokenDiscord.get_time_by_token(token)
            delay: int = datastore.cooldown - abs(min_token_time - current_time)
            datastore.delay = delay
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

    @classmethod
    @logger.catch
    def __get_data_from_api(cls, datastore: 'DataStore') -> dict:
        session = requests.Session()
        session.headers['authorization'] = datastore.token
        limit = 100
        url = datastore.channel_url + f'{datastore.channel}/messages?limit={limit}'
        proxies = {
            "http": f"http://{PROXY_USER}:{PROXY_PASSWORD}@{datastore.proxy}/"
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
                result: dict = cls.__data_filter(data=data, datastore=datastore)
                print("LEN RESULT:", len(result))
        else:
            logger.error(f"API request error: {status_code}")

        return result

    @classmethod
    @logger.catch
    def __data_filter(cls, data: dict, datastore: 'DataStore') -> dict:
        messages = []
        replies = [{}]
        result = {}
        summa = 0

        for elem in data:
            reply: str = elem.get("referenced_message", {}).get("author", {}).get("id", '')
            mentions: tuple = tuple(filter(lambda x: x.get("id", '') == datastore.my_discord_id, elem.get("mentions", [])))
            author: str = elem.get("author")
            if any(mentions) or reply == datastore.my_discord_id:
                if author not in UserTokenDiscord.get_all_discord_id(token=datastore.token):
                    replies.append({
                        "token": datastore.token,
                        "author": author,
                        "text": elem.get("content", ''),
                        "id":  elem.get("id", '')
                    })

            message = elem.get("content")
            message_time = elem.get("timestamp")
            mes_time = datetime.datetime.fromisoformat(message_time).replace(tzinfo=None)
            if datastore.mate_id == elem["author"]["id"]:
                delta = datetime.datetime.utcnow().replace(tzinfo=None) - mes_time
                if delta.seconds < datastore.last_message_time:
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

    @classmethod
    @logger.catch
    def __get_random_message(cls, seq: list) -> dict:
        """Возвращает случайно выбранный словарь из списка"""

        return random.choice(tuple(seq))


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

        answer: str = self.__send_message_to_discord_channel(text)
        logger.info(f"Результат отправки сообщения в дискорд: {answer}")
        UserTokenDiscord.update_token_time(self.__datastore.token)

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
