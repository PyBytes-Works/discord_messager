from typing import List, Dict, Any
from collections import namedtuple

from config import logger


class TokenData:
    """
    Класс для хранения текущих данных для отправки и получения сообщений дискорда

    Methods
        check_user_data
        save_token_data
    """

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
        self.data_for_send: dict = {}
        self.text_to_send: str = ''
        self.__all_tokens_ids: List[str] = []
        self.user_channel_pk: int = 0
        self.replies: List[dict] = []

    @logger.catch
    def update(self, token: str, token_data: namedtuple):
        self.token: str = token
        self.proxy: str = token_data.proxy
        self.channel: int = token_data.channel_id
        self.guild: int = token_data.guild_id
        self.cooldown: int = token_data.cooldown
        self.mate_id: str = token_data.mate_discord_id
        self.my_discord_id: str = token_data.token_discord_id
        self.user_channel_pk: int = token_data.user_channel_pk

    @property
    def all_tokens_ids(self) -> List[str]:
        return self.__all_tokens_ids

    @all_tokens_ids.setter
    def all_tokens_ids(self, all_tokens: List[str]):
        if not all_tokens:
            return
        self.__all_tokens_ids = all_tokens

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
