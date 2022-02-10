import asyncio
import random

import aiohttp
import aiohttp.client_exceptions

from config import logger
from models import UserTokenDiscord


class DataStore:
    """
    Класс для хранения текущих данных для отправки и получения сообщений дискорда

    Methods
        check_user_data
        save_token_data
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
        self.__CURRENT_MESSAGE_ID: int = 0
        self.__DISCORD_USER_TOKEN: str = ''
        self.__PROXY: str = ''
        self.__CHANNEL: int = 0
        self.__GUILD: int = 0
        self.__TOKEN_COOLDOWN: int = 0
        self.__MATE_DISCORD_ID: str = ''
        self.__DELAY: int = 0
        self.__MY_DISCORD_ID: str = ''

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
            url: str = cls.__DISCORD_BASE_URL + f'{channel}/messages?limit={limit}'
            result: str = 'bad token'
            try:
                async with session.get(url=url, proxy=f"http://{proxy}", ssl=False, timeout=3) as response:
                # async with session.get(url=url, timeout=10) as response:
                    if response.status == 200:
                        result = token
            except cls.__EXCEPTIONS as err:
                logger.info(f"Token check Error: {err}")

        return result

    def save_token_data(self, token: str):
        self.token: str = token
        token_data: dict = UserTokenDiscord.get_info_by_token(token)
        self.proxy: str = token_data.get("proxy")
        self.channel: int = token_data.get("channel")
        self.guild: int = token_data.get("guild")
        self.cooldown: int = token_data.get("cooldown")
        self.mate_id: str = token_data.get("mate_id")
        self.my_discord_id: str = token_data.get("discord_id")

    @property
    def my_discord_id(self) -> str:
        return self.__MY_DISCORD_ID

    @my_discord_id.setter
    def my_discord_id(self, my_discord_id: str):
        self.__MY_DISCORD_ID = my_discord_id

    @property
    def mate_id(self) -> str:
        return self.__MATE_DISCORD_ID

    @mate_id.setter
    def mate_id(self, mate_id: str):
        self.__MATE_DISCORD_ID = mate_id

    @property
    def last_message_time(self) -> float:
        return self.__TOKEN_COOLDOWN + 60

    @property
    def delay(self) -> int:
        return self.__DELAY

    @delay.setter
    def delay(self, delay: int):
        self.__DELAY = delay

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


class UserDataStore:
    """
    Класс для хранения экземпляров классов данных (ID сообщения в дискорде, время и прочая)
    для каждого пользователя телеграма.
    Инициализируется при запуске бота.
    """
    __VOCABULARY: list = []

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

    @logger.catch
    def get_random_message_from_vocabulary(self) -> str:
        vocabulary: list = self.__get_vocabulary()

        length = len(vocabulary)
        try:
            index = random.randint(0, length - 1)
            text = vocabulary.pop(index)
        except ValueError as err:
            logger.error(f"ERROR: __get_random_message_from_vocabulary: {err}")
            return "Vocabulary error"

        self.__set_vocabulary(vocabulary)

        return text

    @classmethod
    @logger.catch
    def __get_vocabulary(cls) -> list:
        if not cls.__VOCABULARY:
            cls.__update_vocabulary()

        return cls.__VOCABULARY

    @classmethod
    @logger.catch
    def __set_vocabulary(cls, vocabulary: list):
        if isinstance(vocabulary, list):
            if not vocabulary:
                cls.__update_vocabulary()
            else:
                cls.__VOCABULARY = vocabulary

    @classmethod
    @logger.catch
    def __update_vocabulary(cls, file_name: str = "vocabulary_en.txt"):
        with open(file_name, 'r', encoding='utf-8') as f:
            cls.__VOCABULARY = f.readlines()


# initialization user data storage
users_data_storage = UserDataStore()
