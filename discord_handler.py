import datetime
import os
import random
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

from models import UserTokenDiscord
from utils import save_data_to_json
from config import logger
from dotenv import load_dotenv


load_dotenv()

PROXY_USER = os.getenv("PROXY_USER")
PROXY_PASSWORD = os.getenv("PROXY_PASSWORD")

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

    __DISCORD_BASE_URL: str = f'https://discord.com/api/v9/channels/'
    __EXCEPTIONS: tuple = (
        asyncio.exceptions.TimeoutError,
        aiohttp.client_exceptions.ServerDisconnectedError,
        aiohttp.client_exceptions.ClientProxyConnectionError,
        aiohttp.client_exceptions.ClientHttpProxyError,
        aiohttp.client_exceptions.ClientOSError,
        aiohttp.client_exceptions.TooManyRedirects,
        ConnectionResetError
    )

    def __init__(self, telegram_id: str):
        self.telegram_id: str = telegram_id
        self.__MIN_MESSAGE_LENGTH: int = INIT_LENGTH
        self.__LANGUAGE: str = INIT_USER_LANGUAGE
        self.__CURRENT_MESSAGE_ID: int = 0
        self.__CURRENT_TIME_MESSAGE: float = 0
        self.__DISCORD_USER_TOKEN: str = ''
        self.__PROXY: str = ''
        self.__CHANNEL: int = 0
        self.__GUILD: int = 0
        self.__MAX_TIME_MESSAGE_VALUE: int = 600
        self.__TOKEN_COOLDOWN: int = 0

    @classmethod
    async def check_user_data(cls, token: str, proxy: str, channel: int) -> dict:
        """Returns checked dictionary for user data

        Save valid data to instance variables """

        result = {}
        async with aiohttp.ClientSession() as session:
            session.headers['authorization'] = token
            # result["proxy"] = await cls.__check_proxy(session=session, proxy=proxy)
            # if result["proxy"] != "bad proxy":
            result["token"] = await cls.__check_token(session=session, token=token, proxy=proxy, channel=channel)
            if result["token"] != "bad token":
                result["channel"] = channel

        return result

    @classmethod
    async def __check_channel(cls, session, token: str, channel: int) -> str:
        """Returns valid channel else 'bad channel'"""

        session.headers['authorization'] = token
        limit = 1
        url = cls.__DISCORD_BASE_URL + f'{channel}/messages?limit={limit}'
        result = 'bad channel'
        try:
            async with session.get(url=url, timeout=3) as response:
                if response.status == 200:
                    result = channel
        except cls.__EXCEPTIONS as err:
            logger.info(f"Channel check Error: {err}")
        print(f"CHECK CHANNEL RESULT: {result}")
        return result

    @classmethod
    async def __check_proxy(cls, session, proxy: str) -> str:
        """Returns valid proxy else 'bad proxy'"""

        url = "http://icanhazip.com"
        result = 'bad proxy'
        try:
            async with session.get(url=url, proxy=f"http://{proxy}", ssl=False, timeout=3) as response:
                if response.status == 200:
                    result = proxy
        except cls.__EXCEPTIONS as err:
            logger.info(f"Proxy check Error: {err}")

        return result

    @classmethod
    async def __check_token(cls, session, token: str, proxy: str, channel: int) -> str:
        """Returns valid token else 'bad token'"""
        session.headers['authorization'] = token
        limit = 1
        url = cls.__DISCORD_BASE_URL + f'{channel}/messages?limit={limit}'
        result = 'bad token'
        try:
            # async with session.get(url=url, proxy=f"http://{proxy}", ssl=False, timeout=3) as response:
            async with session.get(url=url) as response:
                if response.status == 200:
                    result = token
        except cls.__EXCEPTIONS as err:
            logger.info(f"Token check Error: {err}")
        return result

    def save_token_data(self, token: str):
        self.token = token
        token_data = UserTokenDiscord.get_info_by_token(token)
        self.proxy = token_data.get("proxy")
        self.channel = token_data.get("channel")
        self.language = token_data.get("language")
        self.guild = token_data.get("guild")
        self.cooldown = token_data.get("cooldown")

    @property
    def message_time(self) -> int:
        return self.__MAX_TIME_MESSAGE_VALUE

    @message_time.setter
    def message_time(self, message_time: int):
        self.__MAX_TIME_MESSAGE_VALUE = message_time

    @property
    def cooldown(self) -> int:
        return self.__TOKEN_COOLDOWN

    @cooldown.setter
    def cooldown(self, cooldown: int):
        self.__TOKEN_COOLDOWN = cooldown

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

        return channel if channel else 'no channel'

    @channel.setter
    def channel(self, channel: str):
        self.__CHANNEL = channel

    @property
    def guild(self) -> str:
        guild = self.__GUILD

        return guild if guild else 'no guild'

    @guild.setter
    def guild(self, guild: str):
        self.__GUILD = guild

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
    def add_or_update(self, telegram_id: str, data: 'DataStore') -> None:
        """Сохраняет экземпляр класса пользователя"""

        self.__instance.update(
            {
                telegram_id: data
            }
        )


class MessageReceiver:

    """Класс парсит сообщения из ответа API дискорда, выбирает случайное и отправляет оператору."""

    @classmethod
    @logger.catch
    def __translate_to_russian(cls, message: str) -> str:
        return Translator.translate(text=message, source="en", target="ru")

    @classmethod
    @logger.catch
    def __get_data_from_api(cls, datastore: 'DataStore'):
        session = requests.Session()
        session.headers['authorization'] = datastore.token
        limit = 100
        url = datastore.channel_url + f'{datastore.channel}/messages?limit={limit}'
        proxies = {
            "http": f"http://{PROXY_USER}:{PROXY_PASSWORD}@{datastore.proxy}/",
            # "https": f"http://{PROXY_USER}:{PROXY_PASSWORD}@{datastore.proxy}/"
        }
        response = session.get(url=url, proxies=proxies)
        status_code = response.status_code
        # print(response.text, status_code)
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
                result = cls.__data_filter(data=data, datastore=datastore)
                save_data_to_json(result, "formed.json")
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
            message_time = int(datetime.datetime.fromisoformat(message_time).timestamp())
            if int(datetime.datetime.now().timestamp()) - message_time < datastore.message_time:
                if len(message) > datastore.length:
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

        middle_len = summa // len(data)
        print('Средняя длина сообщения:', middle_len)
        print('Выбрано сообщений:', len(result))

        return result

    @classmethod
    @logger.catch
    def __get_random_message(cls, seq: list) -> dict:
        """Возвращает случайно выбранный словарь из списка"""

        return random.choice(tuple(seq))

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
        print("Ready tokens: ", len(tokens_for_job))
        if tokens_for_job:
            random_token: str = random.choice(tokens_for_job)
            result["token"]: str = random_token
            datastore.save_token_data(random_token)
        else:
            min_token_data: dict = min(all_tokens, key=lambda x: x.get('time'))
            token: str = tuple(min_token_data)[0]
            datastore.save_token_data(token)
            min_token_time: int = UserTokenDiscord.get_time_by_token(token)
            delay: int = datastore.cooldown - abs(min_token_time - current_time)
            text = "seconds"
            if delay > 60:
                minutes: int = delay // 60
                seconds: int = delay % 60
                if minutes < 10:
                    minutes: str = f"0{minutes}"
                if seconds < 10:
                    seconds: str = f'0{seconds}'
                delay: str = f"{minutes}:{seconds}"
                text = "minutes"
            result["message"] = (f"В данный момент все токены заняты. Подождите {delay} {text}. "
                                 f"Затем нажмите /start")

        return result

    @classmethod
    @logger.catch
    def get_message(cls, datastore: 'DataStore') -> dict:
        """Получает данные из АПИ, выбирает случайное сообщение и возвращает ID сообщения
        и само сообщение"""

        result = {"work": False, "message": "no messages"}
        selected_data: dict = cls.__select_token_for_work(datastore=datastore)
        result_message: str = selected_data["message"]
        token: str = selected_data.get("token", None)
        if token is not None:
            datastore.token = token
            cls.__get_data_from_api(datastore=datastore)

            data: List[dict] = cls.__get_data_from_api(datastore=datastore)
            if not data:
                return result
            result_data: dict = cls.__get_random_message(data)
            id_message: int = int(result_data["id"])
            result_message: str = result_data["message"]

            datastore.current_message_id = id_message
            # datastore.current_time = datetime.datetime.now().timestamp()
            if datastore.language == "en":
                result_message: str = cls.__translate_to_russian(result_message)
            print(f"\nID for reply: {id_message}"
                  f"\nMessage: {result_message}")
            result["work"] = True
        result.update({"message": result_message})

        return result


class MessageSender:
    """Класс отправляет сообщение, принятое из телеграма в дискорд канал"""

    @classmethod
    @logger.catch
    def send_message(cls, text: str, datastore: 'DataStore') -> str:
        """Отправляет данные в канал дискорда, возвращает результат отправки."""

        answer: str = cls.__send_message_to_discord_channel(text=text, datastore=datastore)
        logger.info(f"Результат отправки сообщения в дискорд: {answer}")
        UserTokenDiscord.update_token_time(datastore.token)

        return answer

    @classmethod
    @logger.catch
    def __send_message_to_discord_channel(cls, text: str, datastore: 'DataStore') -> str:
        """Отправляет данные в API, возвращает результат отправки."""

        if not datastore.current_message_id:
            return ("Нет ИД сообщения, на которое нужно ответить. "
                      "\nСперва нужно запросить данные из АПИ.")

        if datastore.language == 'en':
            text = cls.__translate_to_english(text)

        data = {
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
        }

        session = requests.Session()
        session.headers['authorization'] = datastore.token
        answer = 'Начало отправки'
        url = datastore.channel_url + f'{datastore.channel}/messages?'
        proxies = {
            "http": f"http://{PROXY_USER}:{PROXY_PASSWORD}@{datastore.proxy}/",
            # "https": f"http://{PROXY_USER}:{PROXY_PASSWORD}@{datastore.proxy}/"
        }
        response = session.post(url=url, json=data, proxies=proxies)

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

        return answer

    @classmethod
    @logger.catch
    def __translate_to_english(cls, message: str) -> str:
        return Translator.translate(text=message, source="ru", target="en")


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


# initialization user data storage
users_data_storage = UserDataStore()
