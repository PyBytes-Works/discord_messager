import datetime
from typing import List
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
        self.__telegram_id: str = telegram_id
        self.__current_message_id: int = 0
        self.__token: str = ''
        self.__proxy: str = ''
        self.__channel: int = 0
        self.__guild: int = 0
        self.__cooldown: int = 0
        self.__mate_discord_id: str = ''
        self.__delay: int = 0
        self.__new_delay: int = 0
        self.__my_discord_id: str = ''
        self.__data_for_send: dict = {}
        self.__text_to_send: str = ''
        self.__user_channel_pk: int = 0
        self.__token_name: str = ''
        self.__token_time_delta: int = 0
        self.__all_tokens_ids: List[str] = []
        self.__last_message_time: float = 0
        self.__end_cooldown_time: float = 0
        self.__is_deleted: bool = False
        self.__token_pk: int = 0

    @logger.catch
    def update_data(
            self,
            token_data: namedtuple,
            mate_id: str
    ) -> 'TokenData':
        self.token: str = token_data.token
        self.proxy: str = token_data.proxy
        self.channel: int = token_data.channel_id
        self.guild: int = token_data.guild_id
        self.cooldown: int = token_data.cooldown
        self.mate_id: str = mate_id
        self.my_discord_id: str = token_data.token_discord_id
        self.user_channel_pk: int = token_data.user_channel_pk
        self.token_name: str = token_data.token_name
        self.last_message_time: float = token_data.last_message_time.timestamp()
        self.token_pk: int = token_data.token_pk
        self.update_end_cooldown_time()

        return self

    def delete_token(self):
        """Устанавливает флаг для удаления токена"""

        self.__is_deleted = True

    def update_end_cooldown_time(self, now: bool = False):
        if now:
            self.update_last_message_time_now()
        self.__end_cooldown_time = self.__last_message_time + self.__cooldown

    def update_last_message_time_now(self):
        self.__last_message_time = int(datetime.datetime.utcnow().replace(tzinfo=None).timestamp())

    @property
    def last_message_time(self) -> float:
        return self.__last_message_time

    @last_message_time.setter
    def last_message_time(self, data: float):
        if not isinstance(data, float):
            raise TypeError(f"Last message time should be float got {type(data)}: value: {data}")
        self.__last_message_time = data

    @property
    def text_to_send(self) -> str:
        return self.__text_to_send

    @text_to_send.setter
    def text_to_send(self, data: str):
        if not isinstance(data, str):
            raise TypeError(f"Data for send should be string got {type(data)}: value: {data}")
        self.__text_to_send = data

    @property
    def data_for_send(self) -> dict:
        return self.__data_for_send

    @data_for_send.setter
    def data_for_send(self, data: dict):
        if not isinstance(data, dict):
            raise TypeError(f"Text for send should be dictionary got {type(data)}: value: {data}")
        self.__data_for_send = data

    @property
    def telegram_id(self) -> str:
        return self.__telegram_id

    @property
    def user_channel_pk(self) -> int:
        return self.__user_channel_pk

    @user_channel_pk.setter
    def user_channel_pk(self, data: int):
        if not isinstance(data, int):
            raise TypeError(f"User channel pk should be integer got {type(data)}: value: {data}")
        self.__user_channel_pk = data

    @property
    def end_cooldown_time(self) -> float:
        return self.__end_cooldown_time

    @property
    def token_name(self) -> str:
        return self.__token_name

    @token_name.setter
    def token_name(self, data: str):
        if not isinstance(data, str):
            raise TypeError(f"Token name should be string got {type(data)}: value: {data}")
        self.__token_name = data

    @property
    def token_pk(self) -> int:
        return self.__token_pk

    @token_pk.setter
    def token_pk(self, data: int):
        if not isinstance(data, int):
            raise TypeError(f"Token pk should be integer got {type(data)}: value: {data}")
        self.__token_pk = data

    @property
    def need_to_delete(self) -> bool:
        return self.__is_deleted

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
        return self.__my_discord_id

    @my_discord_id.setter
    def my_discord_id(self, my_discord_id: str):
        self.__my_discord_id = my_discord_id

    @property
    def token_time_delta(self) -> int:
        return self.__token_time_delta

    @token_time_delta.setter
    def token_time_delta(self, value: int):
        self.__token_time_delta = value

    @property
    def mate_id(self) -> str:
        return self.__mate_discord_id

    @mate_id.setter
    def mate_id(self, data: str):
        self.__mate_discord_id = data

    @property
    def max_message_search_time(self) -> float:
        """Максимальное время поиска сообщения
        (для поиска сообщений позднее данного времени)"""

        return self.__cooldown + self.token_time_delta

    @property
    def delay(self) -> int:
        return self.__delay

    @delay.setter
    def delay(self, delay: int):
        self.__delay = delay

    @property
    def new_delay(self) -> int:
        return self.__new_delay

    @new_delay.setter
    def new_delay(self, data: int):
        if not isinstance(data, int):
            raise TypeError(f"new_delay should be integer got {type(data)}: value: {data}")
        self.__new_delay = data

    @property
    def cooldown(self) -> int:
        return self.__cooldown

    @cooldown.setter
    def cooldown(self, cooldown: int):
        self.__cooldown = cooldown

    @property
    def current_message_id(self) -> int:
        return self.__current_message_id

    @current_message_id.setter
    def current_message_id(self, message_id: int):
        self.__current_message_id = message_id

    @property
    def channel(self) -> str:
        channel = self.__channel

        return channel if channel else ''

    @channel.setter
    def channel(self, channel: str):
        self.__channel = channel

    @property
    def guild(self) -> str:
        guild = self.__guild

        return guild if guild else ''

    @guild.setter
    def guild(self, guild: str):
        self.__guild = guild

    @property
    def token(self) -> str:
        return self.__token if self.__token else ''

    @token.setter
    def token(self, token: str):
        self.__token = token

    @property
    def proxy(self) -> str:
        return self.__proxy if self.__proxy else ''

    @proxy.setter
    def proxy(self, proxy: str) -> None:
        self.__proxy = proxy
