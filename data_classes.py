import os
import random

from config import logger
from models import Token


class TokenDataStore:
    """
    Класс для хранения текущих данных для отправки и получения сообщений дискорда

    Methods
        check_user_data
        save_token_data
    """

    __DISCORD_BASE_URL: str = f'https://discord.com/api/v9/channels/'

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

    def create_datastore_data(self, token: str):
        self.token: str = token
        token_data: dict = Token.get_info_by_token(token)
        self.proxy: str = token_data.get("proxy")
        self.channel: int = token_data.get("channel")
        self.guild: int = token_data.get("guild")
        self.cooldown: int = token_data.get("cooldown")
        self.mate_id: str = token_data.get("mate_id")
        self.my_discord_id: str = token_data.get("discord_id")

    @classmethod
    def get_channel_url(cls) -> str:
        return cls.__DISCORD_BASE_URL

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
        return self.__TOKEN_COOLDOWN + 120

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


class InstancesStorage:
    """
    Класс для хранения экземпляров классов данных (ID сообщения в дискорде, время и прочая)
    для каждого пользователя телеграма.
    Инициализируется при запуске бота.
    """

    def __init__(self):
        self.__instance = {}

    @logger.catch
    def get_instance(self, telegram_id: str) -> 'TokenDataStore':
        """Возвращает текущий экземпляр класса для пользователя'"""

        return self.__instance.get(telegram_id, {})

    @logger.catch
    def add_or_update(self, telegram_id: str, data: 'TokenDataStore') -> None:
        """Сохраняет экземпляр класса пользователя"""

        self.__instance.update(
            {
                telegram_id: data
            }
        )


class Vocabulary:
    """Работает с файлом фраз для отправки в дискорд"""

    __VOCABULARY: list = []
    __PATH_TO_FILE: str = "./db/vocabulary_en.txt"

    @classmethod
    @logger.catch
    def get_message(cls) -> str:
        vocabulary: list = cls.__get_vocabulary()

        length: int = len(vocabulary)
        try:
            string_index: int = random.randint(0, length - 1)
            message_text: str = vocabulary.pop(string_index)
            cls.__set_vocabulary(vocabulary)
        except (ValueError, TypeError, FileNotFoundError) as err:
            logger.error(f"ERROR: __get_random_message_from_vocabulary: {err}")
            return "Vocabulary error"
        if len(message_text) > 40:
            return cls.get_message()
        return message_text

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
        else:
            raise TypeError("__set_vocabulary error: ")

    @classmethod
    @logger.catch
    def __update_vocabulary(cls, file_name: str = None):
        if not file_name:
            file_name = cls.__PATH_TO_FILE
        if os.path.exists(file_name):
            with open(file_name, 'r', encoding='utf-8') as f:
                cls.__VOCABULARY = f.readlines()
        else:
            raise FileNotFoundError(f"__update_vocabulary: {file_name} error: ")


# initialization user data storage
users_data_storage = InstancesStorage()
