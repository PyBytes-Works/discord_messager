import asyncio

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

    @classmethod
    async def check_user_data(cls, token: str, proxy: str, channel: int) -> dict:
        """Returns checked dictionary for user data

        Save valid data to instance variables """

        result = {}
        async with aiohttp.ClientSession() as session:
            session.headers['authorization'] = token
            result["token"] = await cls.__check_token(
                session=session, token=token, proxy=proxy, channel=channel
            )
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
        self.guild: int = token_data.get("guild")
        self.cooldown: int = token_data.get("cooldown")
        self.mate_id: str = token_data.get("mate_id")

    @property
    def mate_id(self) -> str:
        return self.__MATE_DISCORD_ID

    @mate_id.setter
    def mate_id(self, mate_id: str):
        self.__MATE_DISCORD_ID = mate_id

    @property
    def last_message_time(self) -> float:
        return self.__TOKEN_COOLDOWN + 180

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

    @classmethod
    @logger.catch
    def __update_vocabulary(cls, file_name: str = "vocabulary_en.txt"):
        with open(file_name, 'r', encoding='utf-8') as f:
            cls.__VOCABULARY = f.readlines()

    @classmethod
    @logger.catch
    def get_vocabulary(cls) -> list:
        if not cls.__VOCABULARY:
            cls.__update_vocabulary()

        return cls.__VOCABULARY

    @classmethod
    @logger.catch
    def set_vocabulary(cls, vocabulary: list):
        if isinstance(vocabulary, list):
            if not vocabulary:
                cls.__update_vocabulary()
            else:
                cls.__VOCABULARY = vocabulary

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


# initialization user data storage
users_data_storage = UserDataStore()
