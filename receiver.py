import datetime
import random
from typing import List

import requests

from config import LENGTH, DISCORD_USER_TOKEN, PARSING_CHAT_ID, USER_LANGUAGE
from utils import save_data_to_json


class MessageReceiver:

    """Класс парсит сообщения из ответа API дискорда, выбирает случайное и отправляет оператору."""

    LANGUAGE = USER_LANGUAGE
    CURRENT_MESSAGE_ID: int = None
    CURRENT_TIME_MESSAGE: float = None

    @classmethod
    def __translate_to_russian(cls, message: str) -> str:
        return message

    @classmethod
    def __handling_received_data(cls, data: dict) -> list:
        result = []
        summa = 0

        for elem in data:
            message = elem.get("content")
            if len(message) > LENGTH:
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
    def __get_data_from_api(cls):
        session = requests.Session()
        session.headers['authorization'] = DISCORD_USER_TOKEN
        limit = 100
        response = session.get(f'https://discord.com/api/v9/channels/{PARSING_CHAT_ID}/messages?limit={limit}')
        status_code = response.status_code
        result = {}
        if status_code == 200:
            try:
                data = response.json()
            except Exception as err:
                print("JSON ERROR", err)
            else:
                print(f"Data requested {limit}\n"
                      f"Data received: {len(data)}")
                save_data_to_json(data)
                result = cls.__handling_received_data(data)
                save_data_to_json(result, "formed.json")
        else:
            print("API request error:", status_code)

        return result

    @classmethod
    def __message_selector(cls, seq: list) -> dict:
        return random.choice(tuple(seq))

    @classmethod
    def get_message_data(cls) -> str:
        """Получает данные из АПИ, выбирает случайное сообщение и возвращает ID сообщения
        и само сообщение"""

        data: List[dict] = cls.__get_data_from_api()
        result_data: dict = cls.__message_selector(data)
        id_message: int = int(result_data["id"])
        result_message = result_data["message"]

        cls.CURRENT_MESSAGE_ID = id_message
        cls.CURRENT_TIME_MESSAGE = datetime.datetime.now().timestamp()
        if cls.LANGUAGE == "en":
            result_message: str = cls.__translate_to_russian(result_message)
        print(f"\nID for reply: {id_message}"
              f"\nMessage: {result_message}")

        return result_message
