import datetime
import os
import random
import time
from typing import List
import json
import asyncio
from json.decoder import JSONDecodeError
import aiohttp
import aiohttp.client_exceptions

import requests
from requests.exceptions import (
    Timeout,
    ConnectionError,
    ConnectTimeout,
    RequestException
)

from proxy_utils import get_free_proxies
from utils import save_data_to_json
from config import logger
from dotenv import load_dotenv


load_dotenv()

DISCORD_USER_TOKEN = os.getenv("DESKENT_DISCORD")
DESKENT_MEMBER_ID = os.getenv("DESKENT_MEMBER_ID")
PARSING_CHAT_ID: int = int(os.getenv("PARSING_CHAT_ID"))
PARSING_GUILD_ID: int = int(os.getenv("PARSING_GUILD_ID"))
INIT_USER_LANGUAGE: str = os.getenv("LANGUAGE")
INIT_LENGTH = 10

FOLDER_ID = os.getenv("FOLDER_ID")  # Токен Андрея
OAUTH_TOKEN = os.getenv("OAUTH_TOKEN")  # Токен Андрея

# УДАЛИТЬ ПОСЛЕ ТЕСТОВ
OPERATOR_CHAT_ID = os.getenv("OPERATOR_CHAT_ID")


class DataStore:
    """
    Класс для хранения текущих данных для отправки и получения сообщений дискорда

    Methods
        public
            check_user_data

        getters/setters
            message_time
            channel_url
            current_message_id
            current_time
            language
            channel
            token
            proxy
            length
    """

    def __init__(self, telegram_id: str):
        self.user_id: str = telegram_id
        self.__MIN_MESSAGE_LENGTH: int = INIT_LENGTH
        self.__LANGUAGE: str = INIT_USER_LANGUAGE
        self.__CURRENT_MESSAGE_ID: int = 0
        self.__CURRENT_TIME_MESSAGE: float = 0
        self.__DISCORD_USER_TOKEN: str = ''
        self.__PROXY: str = ''
        self.__CHANNEL: int = 0
        self.__DISCORD_BASE_URL: str = f'https://discord.com/api/v9/channels/'
        self.__MAX_TIME_MESSAGE_VALUE: int = 600
        self.__EXCEPTIONS: tuple = (
            asyncio.exceptions.TimeoutError,
            aiohttp.client_exceptions.ServerDisconnectedError,
            aiohttp.client_exceptions.ClientProxyConnectionError,
            aiohttp.client_exceptions.ClientHttpProxyError,
            aiohttp.client_exceptions.ClientOSError,
            aiohttp.client_exceptions.TooManyRedirects,
            ConnectionResetError
        )

    async def check_user_data(self, token: str, proxy: str, channel: int) -> dict:
        """Returns checked dictionary for user data

        Save valid data to instance variables """
        result = {"token": "bad token"}
        async with aiohttp.ClientSession() as session:
            session.headers['authorization'] = token
            result["channel"] = await self.__check_channel(session=session, token=token, channel=channel)
            if result["channel"] != "bad channel":
                result["proxy"] = await self.__check_proxy(session=session, proxy=proxy)
                self.channel = channel
                if result["proxy"] != "bad proxy":
                    self.proxy = proxy
                    result["token"] = await self.__check_token(session=session, token=token)
                    if result["token"] != "bad token":
                        self.token = token

        return result

    async def __check_channel(self, session, token: str, channel: int) -> str:
        """Returns valid channel else 'bad channel'"""

        session.headers['authorization'] = token
        limit = 1
        url = self.__DISCORD_BASE_URL + f'{channel}/messages?limit={limit}'
        result = 'bad channel'
        try:
            async with session.get(url=url, timeout=3) as response:
                if response.status == 200:
                    result = channel
        except self.__EXCEPTIONS as err:
            logger.info(f"Channel check Error: {err}")

        return result

    async def __check_proxy(self, session, proxy: str) -> str:
        """Returns valid proxy else 'bad proxy'"""

        url = "http://icanhazip.com"
        result = 'bad proxy'
        try:
            async with session.get(url=url, proxy=f"http://{proxy}", ssl=False, timeout=3) as response:
                if response.status == 200:
                    result = proxy
        except self.__EXCEPTIONS as err:
            logger.info(f"Proxy check Error: {err}")

        return result

    async def __check_token(self, session, token: str) -> str:
        """Returns valid token else 'bad token'"""

        session.headers['authorization'] = token
        limit = 1
        url = self.__DISCORD_BASE_URL + f'{self.channel}/messages?limit={limit}'
        result = 'bad token'
        try:
            async with session.get(url=url, proxy=f"http://{self.proxy}", ssl=False, timeout=3) as response:
                if response.status == 200:
                    result = token
        except self.__EXCEPTIONS as err:
            logger.info(f"Token check Error: {err}")

        return result

    @property
    def message_time(self) -> int:
        return self.__MAX_TIME_MESSAGE_VALUE

    @message_time.setter
    def message_time(self, message_time: int):
        self.__MAX_TIME_MESSAGE_VALUE = message_time

    @property
    def channel_url(self) -> str:
        return self.__DISCORD_BASE_URL

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

    @language.setter
    def language(self, language: str):
        self.__LANGUAGE = language

    @property
    def channel(self) -> str:
        channel = self.__CHANNEL

        return channel if channel else 'no token'

    @channel.setter
    def channel(self, channel: str):
        self.__CHANNEL = channel

    @property
    def token(self) -> str:
        spam = self.__DISCORD_USER_TOKEN

        return spam if spam else 'no token'

    @token.setter
    def token(self, token: str):
        self.__DISCORD_USER_TOKEN = token

    @property
    def proxy(self) -> str:
        return self.__PROXY if self.__PROXY else 'no proxy'

    @proxy.setter
    def proxy(self, proxy: str) -> None:
        self.__PROXY = proxy

    @property
    def length(self) -> int:
        return self.__MIN_MESSAGE_LENGTH

    @length.setter
    def length(self, length: int):
        self.__MIN_MESSAGE_LENGTH = length


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

    __STORE_INSTANCE = None

    @classmethod
    @logger.catch
    def __translate_to_russian(cls, message: str) -> str:
        return Translator.translate(text=message, source="en", target="ru")

    @classmethod
    @logger.catch
    def __get_data_from_api(cls):
        session = requests.Session()
        session.headers['authorization'] = cls.__STORE_INSTANCE.token
        limit = 100
        url = cls.__STORE_INSTANCE.channel_url + f'?limit={limit}'
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
            if len(message) > cls.__STORE_INSTANCE.length:
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

        cls.__STORE_INSTANCE = datastore
        cls.__get_data_from_api()
        data: List[dict] = cls.__get_data_from_api()
        result_data: dict = cls.__message_selector(data)
        id_message: int = int(result_data["id"])
        result_message = result_data["message"]

        cls.__STORE_INSTANCE.current_message_id = id_message
        cls.__STORE_INSTANCE.current_time = datetime.datetime.now().timestamp()
        if cls.__STORE_INSTANCE.language == "en":
            result_message: str = cls.__translate_to_russian(result_message)
        print(f"\nID for reply: {id_message}"
              f"\nMessage: {result_message}")

        return result_message


class MessageSender:
    """Класс отправляет сообщение, принятое из телеграма в дискорд канал"""

    __STORE_INSTANCE: 'DataStore' = None
    __MESSAGE_TEXT: str = None

    @classmethod
    @logger.catch
    def __translate_to_english(cls, message: str) -> str:
        return Translator.translate(text=message, source="ru", target="en")

    @classmethod
    @logger.catch
    def __send_message_to_discord_channel(cls) -> str:
        """Отправляет данные в API, возвращает результат отправки."""
        session = requests.Session()
        session.headers['authorization'] = cls.__STORE_INSTANCE.token
        answer = 'Начало отправки'

        if cls.__MESSAGE_TEXT:
            text = cls.__MESSAGE_TEXT
            if cls.__STORE_INSTANCE.language == 'en':
                text = cls.__translate_to_english(cls.__MESSAGE_TEXT)
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
                        "message_id": cls.__STORE_INSTANCE.current_message_id
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
            response = session.post(url=cls.__STORE_INSTANCE.channel_url, json=data)

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

        cls.__STORE_INSTANCE = datastore
        cls.__MESSAGE_TEXT = text

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


async def main(token, proxy, channel):
    """For testing"""
    return await data.check_user_data(token=token, proxy=proxy, channel=channel)


if __name__ == '__main__':
    datastore = UserDataStore()
    # token = get_random_token()
    telegram_id = "12356"
    my_data = DataStore(telegram_id=telegram_id)
    datastore.add_instance(telegram_id=telegram_id, data=my_data)
    # token = "OTMzMTE5MDEzNzc1NjI2MzAy.YfFAmw._X2-nZ6_knM7pK3081hqjdYHrn4"
    data: 'DataStore' = datastore.get_instance(telegram_id=telegram_id)
    # pr = "103.92.114.2:80"
    chat_id = 932256559394861079
    tokens = [
  "OTMzMTE5MDEzNzc1NjI2MzAy.YfFAmw._X2-nZ6_knM7pK3081hqjdYHrn4",
  "OTMzMTE5MDIwOTc3MjUwMzQ2.YfFBFg.JR8vuZzJyQR_dDo3l6tNxXajqeQ",
  "OTMzMTE5MDYwNDIwNDc2OTM5.YfFBag.fPqptdKuRCUnQXmgJg6bYQWMiwA",
  "OTMzMTE5MTA2OTI2OTE1NjQ1.YfFBzw.hMd49iD7F5wLEseaFPL9jSGR_OI",
  "OTMzMTE5MTIzMTc1NjQ5Mzcx.YfFB7A.2PSJGY8x5LgLVv3vZgLSsAAhy4Y",
  "OTMzMTE5MTE2ODE3MTA0OTE2.YfFBug.7xew7zy6RZCHoWBLBYVfYsEd-EQ",
  "OTMzMTE5MDM2ODE0OTE3NzAy.YfFBiQ.snhTlAkzpga0JMyddwukdmgI2Y8",
  "OTMzMTE5MTY4NDM2NDA0MjQ0.YfE_XA.WYJ8VjIn2YL2VPgNuN0i5XX1D1o"
]
    for token in tokens:
        for proxy in get_free_proxies():
            print(f"Отправляю запрос со 100% рабочим токеном через прокси {proxy} в канал {chat_id}:")
            result = {}
            try:
                for i in range(1):
                    res = asyncio.get_event_loop().run_until_complete(main(token=token, proxy=proxy, channel=chat_id))
                    if res.get("token", None):
                        print(f"Попытка № {i + 1}\t: Результат: {res}", file=open('res.txt', 'a', encoding='utf-8'))

                        result.update(
                            {
                                res["token"]: [res["channel"], res["proxy"]]
                            }
                        )
                    time.sleep(1)
            except KeyboardInterrupt:
                print("END")
            else:
                save_data_to_json(result, "parse_tokens.jsoin")
