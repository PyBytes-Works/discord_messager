import datetime
import os
import random
from typing import List

import requests

from utils import save_data_to_json
from config import logger

from dotenv import load_dotenv
load_dotenv()

DISCORD_USER_TOKEN = os.getenv("DESKENT_DISCORD")
DESKENT_MEMBER_ID = os.getenv("DESKENT_MEMBER_ID")
PARSING_CHAT_ID = os.getenv("PARSING_CHAT_ID")
PARSING_GUILD_ID = os.getenv("PARSING_GUILD_ID")
USER_LANGUAGE = os.getenv("LANGUAGE")
OPERATOR_CHAT_ID = os.getenv("OPERATOR_CHAT_ID")
LENGTH = 10


class DataStore:
    """Класс для хранения текущих данных для отправки и получения сообщений дискорда"""

    MIN_LENGTH = LENGTH
    CHANNEL_URL: str = f'https://discord.com/api/v9/channels/{PARSING_CHAT_ID}/messages'
    LANGUAGE: str = USER_LANGUAGE
    CURRENT_MESSAGE_ID: int = None
    CURRENT_TIME_MESSAGE: float = None
    DISCORD_USER_TOKEN: str = DISCORD_USER_TOKEN

    def __init__(self, telegram_id: str):
        self.user_id: str = telegram_id

    @property
    def channel_url(self) -> str:
        return self.CHANNEL_URL

    @property
    def current_message_id(self) -> int:
        return self.CURRENT_MESSAGE_ID

    @current_message_id.setter
    def current_message_id(self, message_id: int):
        self.CURRENT_MESSAGE_ID = message_id

    @property
    def current_time(self) -> float:
        return self.CURRENT_TIME_MESSAGE

    @current_time.setter
    def current_time(self, date: float):
        self.CURRENT_TIME_MESSAGE = date


class UserDataStore:
    """
    Класс для хранения экземпляров классов данных (ID сообщения в дискорде, время и прочая)
    для каждого пользователя телеграма.
    Инициализируется при запуске бота.
    """

    def __init__(self):
        self.__instance = {}

    @logger.catch
    def get_instance(self, telegram_id: str) -> 'DataStore':
        """Возвращает текущий экземпляр класса для пользователя'"""

        return self.__instance.get(telegram_id, {})

    @logger.catch
    def add_instance(self, telegram_id: str, data: 'DataStore') -> None:
        """Сохраняет экземпляр класса пользователя"""

        self.__instance.update(
            {
                telegram_id: data
            }
        )


class MessageReceiver:

    """Класс парсит сообщения из ответа API дискорда, выбирает случайное и отправляет оператору."""

    STORE_INSTANCE = None

    @classmethod
    @logger.catch
    def __translate_to_russian(cls, message: str) -> str:
        return message

    @classmethod
    @logger.catch
    def __translate_to_english(cls, message: str) -> str:
        return message

    @classmethod
    @logger.catch
    def __get_data_from_api(cls):
        session = requests.Session()
        session.headers['authorization'] = cls.STORE_INSTANCE.DISCORD_USER_TOKEN
        limit = 10
        url = cls.STORE_INSTANCE.channel_url + f'?limit={limit}'
        response = session.get(url=url)
        status_code = response.status_code
        result = {}
        if status_code == 200:
            try:
                data = response.json()
            except Exception as err:
                logger.error(f"JSON ERROR: {err}")
            else:
                print(f"Data requested {limit}\n"
                      f"Data received: {len(data)}")
                save_data_to_json(data)
                result = cls.__data_filter(data)
                save_data_to_json(result, "formed.json")
        else:
            logger.error(f"API request error: {status_code}")

        return result

    @classmethod
    @logger.catch
    def __data_filter(cls, data: dict) -> list:
        result = []
        summa = 0

        for elem in data:
            message = elem.get("content")
            if len(message) > cls.STORE_INSTANCE.MIN_LENGTH:
                summa += len(message)
                result.append(
                    {
                        "id": elem.get("id"),
                        "message": message,
                        "channel_id": elem.get("channel_id"),
                        "author": elem.get("author"),
                        "timestamp": elem.get("timestamp")
                    }
                )

        middle_len = summa // len(data)
        print('Средняя длина сообщения:', middle_len)
        print('Выбрано сообщений:', len(result))

        return result

    @classmethod
    @logger.catch
    def __message_selector(cls, seq: list) -> dict:
        """Возвращает случайно выбранный словарь из списка"""

        return random.choice(tuple(seq))

    @classmethod
    @logger.catch
    def get_message(cls, datastore: 'DataStore') -> str:
        """Получает данные из АПИ, выбирает случайное сообщение и возвращает ID сообщения
        и само сообщение"""

        cls.STORE_INSTANCE = datastore
        cls.__get_data_from_api()
        data: List[dict] = cls.__get_data_from_api()
        result_data: dict = cls.__message_selector(data)
        id_message: int = int(result_data["id"])
        result_message = result_data["message"]

        cls.STORE_INSTANCE.current_message_id = id_message
        cls.STORE_INSTANCE.current_time = datetime.datetime.now().timestamp()
        if cls.STORE_INSTANCE.LANGUAGE == "en":
            result_message: str = cls.__translate_to_russian(result_message)
        print(f"\nID for reply: {id_message}"
              f"\nMessage: {result_message}")

        return result_message


class MessageSender:
    """Класс отправляет сообщение, принятое из телеграма в дискорд канал"""

    STORE_INSTANCE: 'DataStore' = None
    MESSAGE_TEXT: str = None

    @classmethod
    @logger.catch
    def __send_message_to_discord_channel(cls) -> str:
        """Отправляет данные в API, возвращает результат отправки."""

        session = requests.Session()
        session.headers['authorization'] = DISCORD_USER_TOKEN
        answer = 'Начало отправки'
        if cls.STORE_INSTANCE.LANGUAGE is not None:
            # data = {"content": f"<@!{cls.STORE_INSTANCE.current_message_id}>{text}",
            #         # "nonce": "??????????",
            #         "tts": "false"}
            data = {
                "content": cls.MESSAGE_TEXT,
                # "nonce": "935150872076222464",
                "tts": "false",
                "message_reference":
                    {
                        "guild_id": PARSING_GUILD_ID,
                        "channel_id": PARSING_CHAT_ID,
                        "message_id": cls.STORE_INSTANCE.current_message_id
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
            }
            response = session.post(url=cls.STORE_INSTANCE.channel_url, json=data)

            status_code = response.status_code
            if status_code == 204:
                answer = "Ошибка 204, нет содержимого."
            elif status_code == 200:
                try:
                    data = response.json()
                except Exception as err:
                    print("JSON ERROR", err)
                else:
                    print(f"Data received: {len(data)}")
                    # save_data_to_json(data, file_name="answer.json")
                    answer = "Message sent"
            else:
                answer = f"API request error: {status_code}"

        else:
            answer = ("Нет ИД сообщения, на которое нужно ответить. "
                      "\nСперва нужно запросить данные из АПИ.")

        return answer

    @classmethod
    @logger.catch
    def send_message(cls, text: str, datastore: 'DataStore') -> str:
        """Отправляет данные в канал дискорда, возвращает результат отправки."""

        cls.STORE_INSTANCE = datastore
        cls.MESSAGE_TEXT = text
        answer = cls.__send_message_to_discord_channel()
        logger.info(f"Результат отправки сообщения в дискорд: {answer}")

        return answer
