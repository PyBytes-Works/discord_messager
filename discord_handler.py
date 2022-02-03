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

from utils import save_data_to_json


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
        data: List[dict] = cls.__get_data_from_api(datastore=datastore)
        if data:
            result_data: dict = cls.__get_random_message(data)
            datastore.current_message_id = int(result_data["id"])
        answer = MessageSender.send_message(datastore=datastore)
        datastore.current_message_id = 0
        if answer != "Message sent":
            result.update({"work": False, "message": answer})
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
    def __get_data_from_api(cls, datastore: 'DataStore'):
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
                result = cls.__data_filter(data=data, datastore=datastore)
                print("LEN RESULT:", len(result))
        else:
            logger.error(f"API request error: {status_code}")

        return result

    @classmethod
    @logger.catch
    def __data_filter(cls, data: dict, datastore: 'DataStore') -> list:
        result = []
        summa = 0

        for elem in data:
            message = elem.get("content")
            message_time = elem.get("timestamp")
            mes_time = datetime.datetime.fromisoformat(message_time).replace(tzinfo=None)
            if datastore.mate_id == elem["author"]["id"]:
                delta = datetime.datetime.utcnow().replace(tzinfo=None) - mes_time
                if delta.seconds < datastore.last_message_time:
                    summa += len(message)
                    result.append(
                        {
                            "id": elem.get("id"),
                            "message": message,
                            "channel_id": elem.get("channel_id"),
                            "author": elem.get("author"),
                            "timestamp": message_time
                        }
                    )

        return result

    @classmethod
    @logger.catch
    def __get_random_message(cls, seq: list) -> dict:
        """Возвращает случайно выбранный словарь из списка"""

        return random.choice(tuple(seq))


class MessageSender:
    """Класс выбирает случайное сообщение из файла и отправляет его в дискорд в ответ на сообщение
    связанного токена
    Возвращает сообщение об ошибке или об успехе"""

    @classmethod
    @logger.catch
    def send_message(cls, datastore: 'DataStore') -> str:
        """Отправляет данные в канал дискорда, возвращает результат отправки."""
        answer: str = cls.__send_message_to_discord_channel(datastore=datastore)
        logger.info(f"Результат отправки сообщения в дискорд: {answer}")
        UserTokenDiscord.update_token_time(datastore.token)

        return answer

    @classmethod
    @logger.catch
    def __send_message_to_discord_channel(cls, datastore: 'DataStore') -> str:
        """Отправляет данные в API, возвращает результат отправки."""
        text = cls.__get_random_message_from_vocabulary()
        data = {
            "content": text,
            "tts": "false",
        }
        if datastore.current_message_id:
            data.update({
                "content": text,
                "tts": "false",
                "message_reference":
                    {
                        "guild_id": datastore.guild,
                        "channel_id": datastore.channel,
                        "message_id": datastore.current_message_id
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
        session = requests.Session()
        session.headers['authorization'] = datastore.token
        url = datastore.channel_url + f'{datastore.channel}/messages?'
        proxies = {
            "http": f"http://{PROXY_USER}:{PROXY_PASSWORD}@{datastore.proxy}/",
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

    @classmethod
    @logger.catch
    def __get_random_message_from_vocabulary(cls) -> str:
        vocabulary: list = users_data_storage.get_vocabulary()

        length = len(vocabulary)
        try:
            index = random.randint(0, length - 1)
            text = vocabulary.pop(index)
        except ValueError as err:
            logger.error(f"ERROR: __get_random_message_from_vocabulary: {err}")
            return "Vocabulary error"

        users_data_storage.set_vocabulary(vocabulary)

        return text
