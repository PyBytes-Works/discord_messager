import datetime
import os
import random
from typing import List
import json
from json.decoder import JSONDecodeError

import requests
from requests.exceptions import (
    Timeout,
    ConnectionError,
    ConnectTimeout,
    RequestException
)

from utils import save_data_to_json
from config import logger
from dotenv import load_dotenv


load_dotenv()

DISCORD_USER_TOKEN = os.getenv("DESKENT_DISCORD")
DESKENT_MEMBER_ID = os.getenv("DESKENT_MEMBER_ID")
PARSING_CHAT_ID: int = int(os.getenv("PARSING_CHAT_ID"))
PARSING_GUILD_ID: int = int(os.getenv("PARSING_GUILD_ID"))
USER_LANGUAGE: str = os.getenv("LANGUAGE")
LENGTH = 10

FOLDER_ID = os.getenv("FOLDER_ID")  # Токен Андрея
OAUTH_TOKEN = os.getenv("OAUTH_TOKEN")  # Токен Андрея

# УДАЛИТЬ ПОСЛЕ ТЕСТОВ
OPERATOR_CHAT_ID = os.getenv("OPERATOR_CHAT_ID")


class DataStore:
    """Класс для хранения текущих данных для отправки и получения сообщений дискорда"""

    def __init__(self, telegram_id: str):
        self.user_id: str = telegram_id
        self.__MIN_LENGTH: int = LENGTH
        self.__CHANNEL_URL: str = f'https://discord.com/api/v9/channels/{PARSING_CHAT_ID}/messages'
        self.__LANGUAGE: str = USER_LANGUAGE
        self.__CURRENT_MESSAGE_ID: int = 0
        self.__CURRENT_TIME_MESSAGE: float = 0
        self.__DISCORD_USER_TOKEN: str = DISCORD_USER_TOKEN

    @property
    def channel_url(self) -> str:
        return self.__CHANNEL_URL

    @property
    def current_message_id(self) -> int:
        return self.__CURRENT_MESSAGE_ID

    @current_message_id.setter
    def current_message_id(self, message_id: int):
        self.__CURRENT_MESSAGE_ID = message_id

    @property
    def current_time(self) -> float:
        return self.__CURRENT_TIME_MESSAGE

    @current_time.setter
    def current_time(self, date: float):
        self.__CURRENT_TIME_MESSAGE = date

    @property
    def language(self):
        return self.__LANGUAGE

    @property
    def token(self):
        return self.__DISCORD_USER_TOKEN

    @property
    def length(self):
        return self.__MIN_LENGTH


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
        return Translator.translate(text=message, source="en", target="ru")

    @classmethod
    @logger.catch
    def __get_data_from_api(cls):
        session = requests.Session()
        session.headers['authorization'] = cls.STORE_INSTANCE.token
        limit = 100
        url = cls.STORE_INSTANCE.channel_url + f'?limit={limit}'
        response = session.get(url=url)
        status_code = response.status_code
        print(response.text, status_code)
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
            if len(message) > cls.STORE_INSTANCE.length:
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
        if cls.STORE_INSTANCE.language == "en":
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
    def __translate_to_english(cls, message: str) -> str:
        return Translator.translate(text=message, source="ru", target="en")

    @classmethod
    @logger.catch
    def __send_message_to_discord_channel(cls) -> str:
        """Отправляет данные в API, возвращает результат отправки."""

        session = requests.Session()
        session.headers['authorization'] = cls.STORE_INSTANCE.token
        answer = 'Начало отправки'

        if cls.MESSAGE_TEXT:
            text = cls.MESSAGE_TEXT
            if cls.STORE_INSTANCE.language == 'en':
                text = cls.__translate_to_english(cls.MESSAGE_TEXT)
            # data = {"content": f"<@!{cls.STORE_INSTANCE.current_message_id}>{text}",
            #         # "nonce": "??????????",
            #         "tts": "false"}
            data = {
                "content": text,
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


class Translator:
    """
    Получает токены для работы с Yandex
    Отправляет сообщение и возвращает те4кст на русском, работает только для английского
    при отправке русского текста вернёт тот же самый текст
    Для работы необходим OAUTH_TOKEN, который можно получить для своего Яндекс-аккаунта по ссылке
    https://cloud.yandex.ru/docs/iam/concepts/authorization/oauth-token
    а также идентификатор каталога FOLDER_ID скопировать со стартовой страницы вашего аккаунта в
    яндекс-облаке:
    https://console.cloud.yandex.ru/
    Актуальность ссылок: 25.01.2022
    """

    __iam_token = ''

    @classmethod
    def translate(cls, text: str, target: str = 'ru', source: str = 'en') -> str:
        """
        Метод принимает текст и возвращает текст на языке цели
        если в тексте будут присутствовать слова на языке источника то они будут переведены
         Слова с опечатками в основном переводятся.
        Если какое то слово не получается перевести, вернётся тоже самое слово которое отправили.

        target и source: str: по умолчанию "ru и en" в зависимости от выбора будет назначен язык
        цель и язык источник
        """

        logger.info('Started translating')
        try:
            cls.__check_iam_token()
        except (ValueError, FileExistsError):
            try:
                cls.__get_iam_token()
            except ValueError as exc:
                logger.exception(f'Ошибка получения A_IM-токена! : {exc}')
                return 'Ошибка получения A_IM-токена!'
        else:
            logger.info('I_AM-token is OK')

        folder_id = FOLDER_ID
        source_language = source
        target_language = target

        body = {
            "targetLanguageCode": target_language,
            "sourceLanguageCode": source_language,
            "texts": text,
            "folderId": folder_id,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer {0}".format(cls.__iam_token)
        }
        try:
            response = requests.post(
                'https://translate.api.cloud.yandex.net/translate/v2/translate',
                json=body,
                headers=headers
            )

            data = response.json()

            result = data.get('translations', [dict()])[0].get('text', text)

        except (Timeout, ConnectionError, ConnectTimeout, RequestException, JSONDecodeError) as exc:
            logger.info(exc)
            raise exc
        return result

    @classmethod
    def __check_iam_token(cls) -> None:
        """
        Проверка наличия и актуальности I_AM токена
        Check I_AM-token
        :return:
        """
        json_file_name = 'iam_token.json'
        if not os.path.exists(json_file_name):
            raise FileExistsError(f'{json_file_name} not found.')
        with open(json_file_name, 'r') as file:
            tk = json.load(file)
        cls.__iam_token = tk.get('iamToken')
        if not cls.__iam_token:
            logger.error('NO I_AM-token')
            raise ValueError('NO I_AM-token')
        exp_time = tk.get('expiresAt').rsplit(sep='.', maxsplit=2)[0]
        expire_time = datetime.datetime.fromisoformat(exp_time)
        delta = expire_time - datetime.datetime.utcnow()
        token_time_actual = delta.seconds // 3600
        if token_time_actual <= 3600:
            logger.warning('Token expired!')
            raise ValueError('Token expired!')

    @classmethod
    def __get_iam_token(cls) -> None:
        """
        Получаем I_AM токен и записываем его в файл json и в атрибут класса __iam_token
        :return:
        """
        p = requests.post(
            "https://iam.api.cloud.yandex.net/iam/v1/tokens",
            json={"yandexPassportOauthToken": OAUTH_TOKEN}
        )

        tk = json.loads(p.text)
        cls.__iam_token = tk.get('iamToken', 'Token_key_error')
        if cls.__iam_token == 'Token_key_error':
            raise ValueError('Ошибка получения iam-токена!')
        with open('iam_token.json', 'w') as file:
            json.dump(tk, file, indent=4, ensure_ascii=False)
        logger.info('\nNew A_IM-token received.')


if __name__ == '__main__':
    print(Translator.translate('message for test testestik wont birdtday'))
